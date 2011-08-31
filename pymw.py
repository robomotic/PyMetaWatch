#!/usr/bin/python
# Quick an dirty MetaWatch client in Python for pybluez.
# Written by Travis Goodspeed on--not for--the Nokia N900.

# This doesn't work with very old versions of the MetaWatch.
# Be sure to use a minimum of 0.7.15 and 1.1.7.

import bluetooth, sys, time;


class MetaWatch:
   def __init__(self, watchaddr=None):
      self.CRC=CRC_CCITT();
      
      while watchaddr==None or watchaddr=="none":
         print "performing inquiry..."
         nearby_devices = bluetooth.discover_devices(lookup_names = True)
         print "found %d devices" % len(nearby_devices)
         for addr, name in nearby_devices:
            print "  %s - '%s'" % (addr, name)
            if name=='Fossil Digital Watch V2':
               watchaddr=addr;
         print "Identified Watch at %s" % watchaddr;

      # MetaWatch doesn't run the Service Discovery Protocol.
      # Instead we manually use the portnumber.
      port=1;
      
      print "Connecting to %s on port %i." % (watchaddr, port);
      sock=bluetooth.BluetoothSocket(bluetooth.RFCOMM);
      self.sock=sock;
      sock.connect((watchaddr,port));
      sock.settimeout(10);  #IMPORTANT Must be patient.
      
      #Grab settings from the watch.
      try:
         print "Connected to %s" % self.getinfo();
         self.setclock();
         self.getclock();
      except:
         print "Connection probably failed.  Continuing anyways."
      #Buzz to indicate connection.
      #self.buzz();
   def close(self):
      """Close the connection."""
      self.sock.close();

   verbose=1;
   def tx(self,msg,rx=True):
      """Transmit a MetaWatch packet.  SFD, Length, and Checksum will be added."""
      #Prepend SFD, length.
      msg="\x01"+chr(len(msg)+4)+msg;
      #Append CRC.
      crc=self.CRC.checksum(msg);
      msg=msg+chr(crc&0xFF)+chr(crc>>8); #Little Endian
      
      self.sock.send(msg);
      if self.verbose: print "Sent message: %s" % hex(msg);
      
      if not rx: return None;
      return self.rx();
   def rx(self):
      data=None;
      #Is there a reply?
      try:
         data=self.sock.recv(32);
         data=data[2:];
      except IOError:pass;
      if self.verbose: print "Received [%s]" % hex(data);
      return data;
   
   def writebuffer(self,mode,row1,data1,row2=None,data2=None):
      """Writes image data to the Draw Buffer.
      You'll need to send activatedisplay() to swap things over when done."""
      
      option=mode; #idle screen, single row.
      if row2!=None: option=option|0x10;
      
      packet="\x40%s%s%s\x00" % (
         chr(option),
         chr(row1),data1[0:12]
         );
      if row2!=None:
         packet="%s%s%s" % (
            packet,
            chr(row2),data2[0:11]);
      self.tx(packet,rx=False);
      
      return;
   def clearbuffer(self,mode=1,filled=True):
      self.loadtemplate(mode,filled);
   def testwritebuffer(self,mode=1):
      m=mode;
      image=["\x00\xFF\x00\xFF\x00\xFF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
             "\xFF\x00\xFF\x00\xFF\x00\xFF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
             ];
      self.loadtemplate(mode=m,filled=1);
      # Blank some rows.
      for foo in range(0,96):
         self.writebuffer(m,
                        foo, image[(foo/8)%2]
                        #);
                        ,foo+40, image[((foo+40)/8)%2]);
         #self.updatedisplay(mode=m);
         time.sleep(0.1);
      self.updatedisplay(mode=m);
   def writeimage(self,mode=0,image="template.bmp", live=False):
      """Write a 1bpp BMP file to the watch in the given mode."""
      import Image;
      im=Image.open(image);
      pix=im.load();
      for y in range(0,96):
         rowstr="";
         rowdat="";
         for x in range(0,96,8):
            byte=0;
            for pindex in range(0,8):
               pixel=pix[x+pindex,y];
               rowstr="%s%i" % (rowstr,pixel);
               #byte=((byte<<1)+pixel);
               byte=((byte>>1)|(pixel<<7));
            rowdat="%s%s" % (rowdat,chr(byte));
         #print rowstr;
         self.writebuffer(mode,
                          y,rowdat)#,
                          #0,rowdat);
         time.sleep(0.1); #rate limiting helps.
         if live:
            self.updatedisplay(mode=mode);
            time.sleep(0.1);
      self.updatedisplay(mode=mode);
   def updatedisplay(self,mode=0,activate=1):
      """Update the display to a particular mode."""
      if activate: mode=mode|0x10;
      self.tx("\x43%s" % chr(mode),rx=False);
   def loadtemplate(self,mode=0,filled=0):
      """Update the display to a particular mode."""
      self.tx("\x44%s%s" % (chr(mode),
                            chr(filled)),
              rx=False);
   def idle(self):
      """Wait a second."""
      #time.sleep(1);
      self.rx();
   def buzz(self):
      """Buzz the buzzer."""
      print "Warning: I don't yet know how to stop the buzzer!";
      self.tx("\x23\x00\x02\x00\x02\x00\x01");
   def gettype(self):
      """Get the version information."""
      devtyperesp=self.tx("\x01\x00");
      devtype=ord(devtyperesp[2]);
      types=["Reserved",
             "Ana-Digi", "Digital",
             "DigitalDev", "AnaDigitalDev"];
      self.devtype=types[devtype];
      print "Identified %s MetaWatch" % self.devtype;
   def getinfostr(self,item=0x00):
      """Get the information string."""
      string=self.tx("\x03\x00%s" % chr(item));
      return string[:len(string)-2];  #Don't include the checksum.
   def getinfo(self):
      """Get all the information strings.""";
      model=self.getinfostr(0);
      version=self.getinfostr(1);
      return "%s %s" % (model,version);
   def setclock(self):
      """Set the date and time of the watch to the system time."""
      ltime=time.localtime();
      #Year in BIG ENDIAN, not LITTLE.
      str="\x07\xdb%s%s%s%s%s%s\x01\x01" % (
         chr(ltime.tm_mon),  #month
         chr(ltime.tm_mday), #day of month
         chr((ltime.tm_wday+1) % 7), #day of week
         chr(ltime.tm_hour), #hour
         chr(ltime.tm_min),  #min
         chr(ltime.tm_sec),  #sec
         );
      self.tx("\x26\x00"+str, rx=False);
   
   def getclock(self):
      """Get the local time from the watch, in order to set it or measure drift."""
      #Year in LITTLE ENDIAN, not BIG.
      data=self.tx("\x27\x00");
      date=data[2:]
      #print "Interpreting %s" % hex(date);
      year=ord(date[1])*256+ord(date[0])
      month=ord(date[2]);
      day=ord(date[3]);
      dayofweek=ord(date[4]);
      hour=ord(date[5]);
      minute=ord(date[6]);
      second=ord(date[6]);
      print "%02i:%02i on %02i.%02i.%04i" % (
         hour, minute,
         day, month, year);
class CRC_CCITT:
   def __init__(self, inverted=True):
      self.inverted=inverted;
      self.tab=256*[[]]
      for i in xrange(256):
         crc=0
         c = i << 8
         for j in xrange(8):
            if (crc ^ c) & 0x8000:
               crc = ( crc << 1) ^ 0x1021
            else:
                  crc = crc << 1
            c = c << 1
            crc = crc & 0xffff
         self.tab[i]=crc;
   def update_crc(self, crc, c):
      c=0x00ff & (c % 256)
      if self.inverted: c=self.flip(c);
      tmp = ((crc >> 8) ^ c) & 0xffff
      crc = (((crc << 8) ^ self.tab[tmp])) & 0xffff
      return crc;
   def checksum(self,str):
      """Returns the checksum of a string.""";
      #crcval=0;
      crcval=0xFFFF;
      for c in str:
        crcval=self.update_crc(crcval, ord(c));
      return crcval;
   def flip(self,c):
      """Flips the bit order, because that's what Fossil wants."""
      l=[0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15];
      return ((l[c&0x0F]) << 4) + l[(c & 0xF0) >> 4];
   def test(self):
      return True;

def hex(str):
  """Returns the hex decoded version of a byte string."""
  toret="";
  if str==None: return "none";
  for c in str:
    toret="%s %02x" % (toret,ord(c));
  return toret;


watchaddr=None;
if len(sys.argv)>1: watchaddr=sys.argv[1];
mw=MetaWatch(watchaddr);

mode=0;
# Put an image on the display.
# First, clear the draw buffer to a filled template.
mw.clearbuffer(mode=mode,filled=True);


imgfile="template.bmp";
if len(sys.argv)>2:
   imgfile=sys.argv[2];

#Push a bird into the buffer.
try:
   mw.writeimage(mode=mode,image=imgfile,live=True);
except:
   print "Error loading image.  Probably not in the working directory.";

#Test the writing function by writing a checker pattern.
#mw.testwritebuffer(mode=mode);

mw.close();
