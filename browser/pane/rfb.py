"""Small shared VNC client for the existing Xvfb desktop (raw/zlib rectangles)."""
import socket
import struct
import threading
import time
import zlib
from PIL import Image
try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
except ImportError:
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives.ciphers import Cipher, modes

class Desktop:
    def __init__(self,host,port,password):
        self.sock=socket.create_connection((host,port),timeout=10)
        self.lock=threading.Lock();self.image_lock=threading.Lock();self.version=0;self.closed=False;self.error=None
        banner=self.read(12)
        if not banner.startswith(b'RFB '):raise RuntimeError('Not a VNC server')
        self.send(b'RFB 003.008\n')
        count=self.read(1)[0];types=self.read(count)
        if 2 not in types:raise RuntimeError('VNC password authentication is unavailable')
        self.send(b'\x02')
        key=bytes(int(f'{c:08b}'[::-1],2) for c in password.encode()[:8].ljust(8,b'\0'))
        cipher=Cipher(TripleDES(key),modes.ECB()).encryptor()
        self.send(cipher.update(self.read(16))+cipher.finalize())
        if struct.unpack('>I',self.read(4))[0]:raise RuntimeError('VNC password authentication failed')
        self.send(b'\x01') # shared: never evict Remmina or another viewer
        header=self.read(24);self.width,self.height=struct.unpack('>HH',header[:4]);self.read(struct.unpack('>I',header[20:])[0])
        self.image=Image.new('RGB',(self.width,self.height))
        fmt=struct.pack('>BBBBHHHBBBxxx',32,24,0,1,255,255,255,16,8,0)
        self.send(b'\0\0\0\0'+fmt)
        self.send(struct.pack('>BBHiii',2,0,3,6,0,-223))
        self.decoder=zlib.decompressobj();self.sock.settimeout(None)
        self.thread=threading.Thread(target=self.receive,daemon=True);self.thread.start()
    def read(self,count):
        result=bytearray()
        while len(result)<count:
            chunk=self.sock.recv(count-len(result))
            if not chunk:raise EOFError('VNC connection closed')
            result.extend(chunk)
        return bytes(result)
    def send(self,data):
        with self.lock:self.sock.sendall(data)
    def request(self,incremental):self.send(struct.pack('>BBHHHH',3,int(incremental),0,0,self.width,self.height))
    def receive(self):
        try:
            self.request(False)
            while not self.closed:
                kind=self.read(1)[0]
                if kind==0:
                    _,count=struct.unpack('>BH',self.read(3))
                    for _ in range(count):
                        x,y,w,h,encoding=struct.unpack('>HHHHi',self.read(12))
                        if encoding==-223:
                            with self.image_lock:
                                self.width,self.height=w,h;self.image=Image.new('RGB',(w,h));self.version+=1
                            continue
                        if encoding==0:data=self.read(w*h*4)
                        elif encoding==6:data=self.decoder.decompress(self.read(struct.unpack('>I',self.read(4))[0]))
                        else:raise RuntimeError(f'Unsupported VNC rectangle {encoding}')
                        rect=Image.frombytes('RGB',(w,h),data,'raw','BGRX')
                        with self.image_lock:self.image.paste(rect,(x,y));self.version+=1
                    time.sleep(.06);self.request(True)
                elif kind==2:pass # Bell
                elif kind==3:
                    header=self.read(7);self.read(struct.unpack('>I',header[3:])[0])
                else:raise RuntimeError(f'Unsupported VNC message {kind}')
        except (OSError,EOFError,RuntimeError,ValueError) as exc:
            if not self.closed:self.error=exc
    def snapshot(self):
        with self.image_lock:return self.version,self.image.copy()
    def key(self,keysym,down):self.send(struct.pack('>BBHI',4,int(down),0,keysym))
    def press(self,keysym,modifiers=()):
        for m in modifiers:self.key(m,True)
        self.key(keysym,True);self.key(keysym,False)
        for m in reversed(modifiers):self.key(m,False)
    def text(self,text):
        # One write keeps paste bursts responsive over SSH.
        data=bytearray()
        for c in text:
            sym=ord(c) if ord(c)<=255 else 0x1000000|ord(c)
            if c=='\n':sym=0xff0d
            for down in (1,0):data.extend(struct.pack('>BBHI',4,down,0,sym))
        self.send(data)
    def pointer(self,x,y,buttons):self.send(struct.pack('>BBHH',5,buttons,max(0,min(self.width-1,x)),max(0,min(self.height-1,y))))
    def close(self):
        self.closed=True
        try:self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        self.sock.close();self.thread.join(timeout=2)
