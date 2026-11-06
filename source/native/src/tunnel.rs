use std::{
    collections::VecDeque,
    io::{self, Read, Write},
    net::TcpStream,
};

use steamworks::{SteamError, networking_sockets::NetConnection, networking_types::SendFlags};

const FRAME_BYTES: usize = 16 * 1024;
const BATCH: usize = 16;

pub(crate) struct Tunnel {
    local: TcpStream,
    inbound: VecDeque<Vec<u8>>,
    inbound_offset: usize,
    outbound: Box<[u8; FRAME_BYTES]>,
    pending: usize,
}

impl Tunnel {
    pub(crate) fn new(local: TcpStream) -> io::Result<Self> {
        local.set_nonblocking(true)?;
        local.set_nodelay(true)?;
        Ok(Self {
            local,
            inbound: VecDeque::new(),
            inbound_offset: 0,
            outbound: Box::new([0; FRAME_BYTES]),
            pending: 0,
        })
    }

    pub(crate) fn pump(&mut self, connection: &mut NetConnection) -> io::Result<bool> {
        // Hold one bounded batch when the local game applies backpressure.
        if self.inbound.is_empty() {
            for message in connection
                .receive_messages(BATCH)
                .map_err(io::Error::other)?
            {
                let data = message.data();
                if data.is_empty() || data.len() > FRAME_BYTES {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "Invalid Steam game frame.",
                    ));
                }
                self.inbound.push_back(data.to_vec());
            }
        }
        while let Some(data) = self.inbound.front() {
            match self.local.write(&data[self.inbound_offset..]) {
                Ok(0) => return Ok(false),
                Ok(written) => {
                    self.inbound_offset += written;
                    if self.inbound_offset == data.len() {
                        self.inbound.pop_front();
                        self.inbound_offset = 0;
                    }
                }
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
                Err(error) => return Err(error),
            }
        }

        for _ in 0..BATCH {
            if self.pending == 0 {
                match self.local.read(&mut self.outbound[..]) {
                    Ok(0) => return Ok(false),
                    Ok(read) => self.pending = read,
                    Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
                    Err(error) => return Err(error),
                }
            }
            match connection.send_message(&self.outbound[..self.pending], SendFlags::RELIABLE) {
                Ok(_) => self.pending = 0,
                Err(SteamError::LimitExceeded) => break,
                Err(error) => return Err(io::Error::other(error)),
            }
        }
        Ok(true)
    }
}
