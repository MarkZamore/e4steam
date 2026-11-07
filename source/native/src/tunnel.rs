use std::{
    collections::VecDeque,
    io::{self, Read, Write},
    net::TcpStream,
};
use steamworks::{SteamError, networking_sockets::NetConnection, networking_types::SendFlags};

const FRAME_BYTES: usize = 16 * 1024;
const BATCH: usize = 16;

/// Drain received bytes after remote closure before closing the game's TCP stream.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Pump {
    Open,
    LocalClosed,
    RemoteDrained,
}

pub(crate) trait Transport {
    fn receive(&mut self, limit: usize) -> io::Result<Vec<Vec<u8>>>;
    /// False means backpressure; retain this exact frame for the next poll.
    fn send(&mut self, bytes: &[u8]) -> io::Result<bool>;
}
impl Transport for NetConnection {
    fn receive(&mut self, limit: usize) -> io::Result<Vec<Vec<u8>>> {
        self.receive_messages(limit)
            .map(|messages| {
                messages
                    .into_iter()
                    .map(|message| message.data().to_vec())
                    .collect()
            })
            .map_err(io::Error::other)
    }
    fn send(&mut self, bytes: &[u8]) -> io::Result<bool> {
        match self.send_message(bytes, SendFlags::RELIABLE) {
            Ok(_) => Ok(true),
            Err(SteamError::LimitExceeded) => Ok(false),
            Err(error) => Err(io::Error::other(error)),
        }
    }
}

pub(crate) struct Tunnel<S = TcpStream> {
    local: S,
    inbound: VecDeque<Vec<u8>>,
    inbound_offset: usize,
    outbound: Box<[u8; FRAME_BYTES]>,
    pending: usize,
    local_write_closed: bool,
}
impl Tunnel {
    pub(crate) fn new(local: TcpStream) -> io::Result<Self> {
        local.set_nonblocking(true)?;
        local.set_nodelay(true)?;
        Ok(Self::with_local(local))
    }
}
impl<S: Read + Write> Tunnel<S> {
    fn with_local(local: S) -> Self {
        Self {
            local,
            inbound: VecDeque::new(),
            inbound_offset: 0,
            outbound: Box::new([0; FRAME_BYTES]),
            pending: 0,
            local_write_closed: false,
        }
    }
    pub(crate) fn queued_bytes(&self) -> (usize, usize) {
        (
            self.inbound.iter().map(Vec::len).sum::<usize>() - self.inbound_offset,
            self.pending,
        )
    }
    pub(crate) fn pump(
        &mut self,
        connection: &mut impl Transport,
        remote_open: bool,
    ) -> io::Result<Pump> {
        // Hold one bounded batch when the local game applies backpressure.
        let mut received = BATCH;
        if self.inbound.is_empty() && !self.local_write_closed {
            let messages = connection.receive(BATCH)?;
            received = messages.len();
            for data in messages {
                if data.is_empty() || data.len() > FRAME_BYTES {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "Invalid Steam game frame.",
                    ));
                }
                self.inbound.push_back(data);
            }
        }
        while let Some(data) = self.inbound.front() {
            match self.local.write(&data[self.inbound_offset..]) {
                Ok(0) => self.local_write_closed = true,
                Ok(written) => {
                    self.inbound_offset += written;
                    if self.inbound_offset == data.len() {
                        self.inbound.pop_front();
                        self.inbound_offset = 0;
                    }
                }
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
                Err(error) if is_local_close(&error) => self.local_write_closed = true,
                Err(error) => return Err(error),
            }
            if self.local_write_closed {
                self.inbound.clear();
                self.inbound_offset = 0;
                break;
            }
        }
        if !remote_open {
            // A full batch may have more behind it. Never send new game data
            // after Steam reports closure, but finish delivering received data.
            return Ok(
                if self.local_write_closed || (self.inbound.is_empty() && received < BATCH) {
                    Pump::RemoteDrained
                } else {
                    Pump::Open
                },
            );
        }
        for _ in 0..BATCH {
            if self.pending == 0 {
                match self.local.read(&mut self.outbound[..]) {
                    Ok(0) => return Ok(Pump::LocalClosed),
                    Ok(read) => self.pending = read,
                    Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
                    // A final Disconnect can precede either EOF or reset.
                    // Bytes already accepted by Steam must still be lingered.
                    Err(error) if is_local_close(&error) => return Ok(Pump::LocalClosed),
                    Err(error) => return Err(error),
                }
            }
            if connection.send(&self.outbound[..self.pending])? {
                self.pending = 0;
            } else {
                break;
            }
        }
        Ok(Pump::Open)
    }
}
fn is_local_close(error: &io::Error) -> bool {
    matches!(
        error.kind(),
        io::ErrorKind::ConnectionReset
            | io::ErrorKind::ConnectionAborted
            | io::ErrorKind::BrokenPipe
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Default)]
    struct Local {
        reads: VecDeque<io::Result<Vec<u8>>>,
        writes: Vec<u8>,
        write_limit: Option<usize>,
        write_closed: bool,
    }
    impl Read for Local {
        fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
            let data = self
                .reads
                .pop_front()
                .unwrap_or_else(|| Err(io::ErrorKind::WouldBlock.into()))?;
            assert!(data.len() <= buffer.len());
            buffer[..data.len()].copy_from_slice(&data);
            Ok(data.len())
        }
    }
    impl Write for Local {
        fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
            if self.write_closed {
                return Err(io::ErrorKind::ConnectionReset.into());
            }
            let length = self.write_limit.unwrap_or(buffer.len()).min(buffer.len());
            if length == 0 {
                return Err(io::ErrorKind::WouldBlock.into());
            }
            self.writes.extend_from_slice(&buffer[..length]);
            if self.write_limit.is_some() {
                self.write_limit = Some(0);
            }
            Ok(length)
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    #[derive(Default)]
    struct Wire {
        inbound: VecDeque<Vec<u8>>,
        sent: Vec<Vec<u8>>,
        blocked: bool,
        receives: usize,
    }
    impl Transport for Wire {
        fn receive(&mut self, limit: usize) -> io::Result<Vec<Vec<u8>>> {
            self.receives += 1;
            Ok((0..limit)
                .filter_map(|_| self.inbound.pop_front())
                .collect())
        }
        fn send(&mut self, bytes: &[u8]) -> io::Result<bool> {
            if self.blocked {
                return Ok(false);
            }
            self.sent.push(bytes.to_vec());
            Ok(true)
        }
    }
    #[test]
    fn final_game_packet_is_enqueued_before_local_eof_or_reset() {
        for ending in [Ok(Vec::new()), Err(io::ErrorKind::ConnectionReset.into())] {
            let mut tunnel = Tunnel::with_local(Local {
                reads: VecDeque::from([Ok(b"disconnect.timeout".to_vec()), ending]),
                ..Local::default()
            });
            let mut wire = Wire::default();
            assert_eq!(tunnel.pump(&mut wire, true).unwrap(), Pump::LocalClosed);
            assert_eq!(wire.sent, [b"disconnect.timeout".to_vec()]);
            assert_eq!(tunnel.queued_bytes(), (0, 0));
        }
    }
    #[test]
    fn backpressure_retains_the_final_frame_before_observing_eof() {
        let mut tunnel = Tunnel::with_local(Local {
            reads: VecDeque::from([Ok(b"final".to_vec()), Ok(Vec::new())]),
            ..Local::default()
        });
        let mut wire = Wire {
            blocked: true,
            ..Wire::default()
        };
        assert_eq!(tunnel.pump(&mut wire, true).unwrap(), Pump::Open);
        assert_eq!(tunnel.queued_bytes(), (0, 5));
        wire.blocked = false;
        assert_eq!(tunnel.pump(&mut wire, true).unwrap(), Pump::LocalClosed);
        assert_eq!(wire.sent, [b"final".to_vec()]);
    }
    #[test]
    fn remote_close_drains_all_batches_and_partial_writes_without_sending() {
        let mut tunnel = Tunnel::with_local(Local {
            write_limit: Some(2),
            ..Local::default()
        });
        let mut wire = Wire {
            inbound: (0..BATCH + 1).map(|_| b"tail".to_vec()).collect(),
            ..Wire::default()
        };
        assert_eq!(tunnel.pump(&mut wire, false).unwrap(), Pump::Open);
        assert_eq!(tunnel.queued_bytes(), (BATCH * 4 - 2, 0));
        assert_eq!(wire.receives, 1);
        assert_eq!(tunnel.pump(&mut wire, false).unwrap(), Pump::Open);
        assert_eq!(wire.receives, 1);
        tunnel.local.write_limit = None;
        assert_eq!(tunnel.pump(&mut wire, false).unwrap(), Pump::Open);
        assert_eq!(tunnel.pump(&mut wire, false).unwrap(), Pump::RemoteDrained);
        assert_eq!(tunnel.local.writes, b"tail".repeat(BATCH + 1));
        assert!(wire.sent.is_empty());
    }
    #[test]
    fn a_reset_local_writer_does_not_discard_its_readable_final_packet() {
        let mut tunnel = Tunnel::with_local(Local {
            write_closed: true,
            reads: VecDeque::from([
                Ok(b"final".to_vec()),
                Err(io::ErrorKind::ConnectionReset.into()),
            ]),
            ..Local::default()
        });
        let mut wire = Wire {
            inbound: VecDeque::from([b"incoming".to_vec()]),
            ..Wire::default()
        };
        assert_eq!(tunnel.pump(&mut wire, true).unwrap(), Pump::LocalClosed);
        assert_eq!(wire.sent, [b"final".to_vec()]);
    }
    #[test]
    fn invalid_wire_frames_are_rejected_before_local_delivery() {
        for frame in [Vec::new(), vec![0; FRAME_BYTES + 1]] {
            let mut tunnel = Tunnel::with_local(Local::default());
            let mut wire = Wire {
                inbound: VecDeque::from([frame]),
                ..Wire::default()
            };
            assert_eq!(
                tunnel.pump(&mut wire, true).unwrap_err().kind(),
                io::ErrorKind::InvalidData
            );
            assert!(tunnel.local.writes.is_empty());
        }
    }
}
