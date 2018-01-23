#!venv/bin/python
# -*- coding: utf-8 -*-
import hashlib
import json
import sys
from socket import *

class clienttcp:
    
    def __init__(self,host,port):
        self.s=socket(AF_INET,SOCK_STREAM)
        self.host=host
        self.port=port
    
    def sendDATA(self,machash,clientData):
        try:
            self.s.connect((self.host,self.port))
            self.s.settimeout(1)
            try:
                data=json.dumps(['DATA',machash,clientData])
                self.s.send(data)
                try:
                    msg=json.loads(self.s.recv(1024))
                    self.s.close
                    if msg[0]=='OK':
                        return True
                    else:
                        return False
                except ValueError:
                    print 'Recived data is not json'
            except ValueError:
                print 'Send data is not json'
            except socket.timeout:
                print 'Connection Timeout'
            except socket.error:
                print 'Cant connect to server'
            self.s.close
            return False
        except:
            return False


machash=hashlib.sha1(sys.argv[8]).hexdigest()

data={
    'NAS_Identifier':sys.argv[1],
    'NAS_IP_Address':sys.argv[2],
    'NAS_Port':sys.argv[3],
    'NAS_Port_Type':sys.argv[4],
    'Calling_Station_Id':sys.argv[5],
    'Framed_IP_Address':sys.argv[6],
    'Called_Station_Id':sys.argv[7],
    'User_Name':sys.argv[8],       
    'Password':sys.argv[9]
    }
    
wynik =clienttcp('127.0.0.1',8888).sendDATA(machash,data)
