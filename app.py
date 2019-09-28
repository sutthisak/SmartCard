import os
import io
import re
import binascii
import datetime
from PIL import Image
from smartcard.System import readers
from smartcard.util import toHexString

# Thailand ID Smartcard
# tis-620 to utf-8
# https://pantip.com/topic/38375161
# TIS-620 ภาษาไทยคือ 0xA0 - 0xFF ส่วน Unicode ภาษาไทยคือ 0x0E00 - 0x0E7F
# ส่วนต่างคือ 0x0E00 - 0xA0 = 0x0D60 ครับ เช่น ก.ไก่ TIS-620 คือ 0xA1 แปลงเป็น Unicode คือ 0xA1 + 0x0D60 = 0x0E01

#def thai2unicode(data):
#    result = ''
#    if isinstance(data, list):
#        for d in data:
#            if 0xA0 <= d <= 0xFF:
#                result += chr(d+0x0D60)
#            else:
#                result += chr(d)
#    else :
#        result = data.decode('tis-620').encode('utf-8')
#    result = re.sub('\#+', ' ', result)
#    return result.strip();

def thai2unicode(data):
    result = ''
    result = bytes(data).decode('tis-620')
    result = re.sub('\#+', ' ', result)
    return result.strip();

# define the APDUs used in this script
# https://github.com/chakphanu/ThaiNationalIDCard/blob/master/APDU.md
# Check card

class ThaiCard:
    SELECT = [0x00, 0xA4, 0x04, 0x00, 0x08]
    THAI_CARD = [0xA0, 0x00, 0x00, 0x00, 0x54, 0x48, 0x00, 0x01]

    # CID
    CMD_CID = [0x80, 0xb0, 0x00, 0x04, 0x02, 0x00, 0x0d]
    # TH Fullname
    CMD_THFULLNAME = [0x80, 0xb0, 0x00, 0x11, 0x02, 0x00, 0x64]
    # EN Fullname
    CMD_ENFULLNAME = [0x80, 0xb0, 0x00, 0x75, 0x02, 0x00, 0x64]
    # Date of birth
    CMD_BIRTH = [0x80, 0xb0, 0x00, 0xD9, 0x02, 0x00, 0x08]
    # Gender
    CMD_GENDER = [0x80, 0xb0, 0x00, 0xE1, 0x02, 0x00, 0x01]
    # Card Issuer
    CMD_ISSUER = [0x80, 0xb0, 0x00, 0xF6, 0x02, 0x00, 0x64]
    # Issue Date
    CMD_ISSUE = [0x80, 0xb0, 0x01, 0x67, 0x02, 0x00, 0x08]
    # Expire Date
    CMD_EXPIRE = [0x80, 0xb0, 0x01, 0x6F, 0x02, 0x00, 0x08]
    # Address
    CMD_ADDRESS = [0x80, 0xb0, 0x15, 0x79, 0x02, 0x00, 0x64]
    # Photo_Part
    CMD_PHOTO = ([0x80, 0xb0, 0x01, 0x7B, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x02, 0x7A, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x03, 0x79, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x04, 0x78, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x05, 0x77, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x06, 0x76, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x07, 0x75, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x08, 0x74, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x09, 0x73, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x0A, 0x72, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x0B, 0x71, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x0C, 0x70, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x0D, 0x6F, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x0E, 0x6E, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x0F, 0x6D, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x10, 0x6C, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x11, 0x6B, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x12, 0x6A, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x13, 0x69, 0x02, 0x00, 0xFF],
                 [0x80, 0xb0, 0x14, 0x68, 0x02, 0x00, 0xFF])

    def __init__(self):
        self.reader = None
        self.readers = None
        self.cid = None
        self.name_th = None
        self.name_en = None
        self.date_of_birth = None
        self.gender = None
        self.card_issuer = None
        self.issue_date = None
        self.expire_date = None
        self.address = None
        self.photo = None
        
    def init_reader(self):
        # get all the available readers
        r = readers()
        if len(r) > 0:
            for readerIndex,readerItem in enumerate(r):
                print(f'DEBUG: Available readers {readerIndex} = {readerItem}')
            self.readers = r
            self.reader = r[0]
            print(f'DEBUG: Using = {self.reader}')

    def __get_data(self, cmd, req = [0x00, 0xc0, 0x00, 0x00]):
        # SW1 และ SW2 มีขนาด 1 byte เป็นข้อมูลบอกสถานะการทำงานของ APDU command ที่ส่งไป
        # เช่น SW1 และ SW2 ที่ทำงานเสร็จโดยไม่มีปัญหา ก็คือ 90 00
        data, sw1, sw2 = self.__connection.transmit(cmd)
        data, sw1, sw2 = self.__connection.transmit(req + [cmd[-1]])
        return [data, sw1, sw2];

    def read_data(self):
        if self.reader == None:
           return None

        self.__connection = self.reader.createConnection()
        self.__connection.connect()
        atr = self.__connection.getATR()
        #print(f'DEBUG: ATR = {toHexString(atr)}')

        if (atr[0] == 0x3B & atr[1] == 0x67):
            req = [0x00, 0xc0, 0x00, 0x01]
        else:
            req = [0x00, 0xc0, 0x00, 0x00]

        # Check card
        data, sw1, sw2 = self.__connection.transmit(self.SELECT + self.THAI_CARD)
        #print(f'DEBUG: Select Applet = {sw1:02X} {sw2:02X}')

        # CID
        data = self.__get_data(self.CMD_CID, req)
        self.cid = thai2unicode(data[0])
        #print(f'DEBUG: CID = {self.cid}')

        # TH Fullname
        data = self.__get_data(self.CMD_THFULLNAME, req)
        self.name_th = thai2unicode(data[0])
        #print(f'DEBUG: TH Fullname = {self.name_th}')

        # EN Fullname
        data = self.__get_data(self.CMD_ENFULLNAME, req)
        self.name_en = thai2unicode(data[0])
        #print(f'DEBUG: EN Fullname = {self.name_en}')

        # Date of birth
        data = self.__get_data(self.CMD_BIRTH, req)
        data = thai2unicode(data[0])
        self.date_of_birth = datetime.datetime(int(data[:4]), int(data[4:6]), int(data[6:8]))
        #print(f'DEBUG: Date of birth = {self.date_of_birth:%Y/%m/%d}')

        # Gender
        data = self.__get_data(self.CMD_GENDER, req)
        self.gender = thai2unicode(data[0])
        #print(f'DEBUG: Gender = {self.gender}')

        # Card Issuer
        data = self.__get_data(self.CMD_ISSUER, req)
        self.card_issuer = thai2unicode(data[0])
        #print(f'DEBUG: Card Issuer = {self.card_issuer}')

        # Issue Date
        data = self.__get_data(self.CMD_ISSUE, req)
        data = thai2unicode(data[0])
        self.issue_date = datetime.datetime(int(data[:4]), int(data[4:6]), int(data[6:8]))
        #print(f'DEBUG: Issue Date = {self.issue_date:%Y/%m/%d}')

        # Expire Date
        data = self.__get_data(self.CMD_EXPIRE, req)
        data = thai2unicode(data[0])
        self.expire_date = datetime.datetime(int(data[:4]), int(data[4:6]), int(data[6:8]))
        #print(f'DEBUG: Expire Date = {self.expire_date:%Y/%m/%d}')

        # Address
        data = self.__get_data(self.CMD_ADDRESS, req)
        self.address = thai2unicode(data[0])
        #print(f'DEBUG: Address: {self.address}')

        # PHOTO
        photo = list()
        for i in self.CMD_PHOTO:
            photo += self.__get_data(i, req)[0]
        self.photo = bytearray(photo)

    def save_picture(self, filename=None):
        if self.reader == None:
           return None

        if filename == None:
           filename = self.cid

        with open(f'{filename}.jpg','wb') as f:
            f.write(self.photo)

    def get_data(self):
        if self.cid == None:
            return {'Error':'No data'}

        data = {
                 'cid':self.cid,
                 'NameTH':self.name_th,
                 'NameEn':self.name_en,
                 'DateOfBirth':self.date_of_birth,
                 'Gender':self.gender,
                 'CardIssuer':self.card_issuer,
                 'IssueDate':self.issue_date,
                 'ExpireDate':self.expire_date,
                 'Address':self.address
               }
        self.save_picture(self.name_en.replace(' ','-'))
        return data

if __name__ == '__main__':
    card = ThaiCard()
    card.init_reader()
    card.read_data()
    for key, value in card.get_data().items():
        print(f'{key} → {value}')