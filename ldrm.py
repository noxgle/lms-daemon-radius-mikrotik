#!venv/bin/python
# -*- coding: utf-8 -*-
import ConfigParser
from collections import deque
import hashlib
import json
import logging
import os.path
from signal import SIGTERM
import socket
import sys
import threading
import time
import select

import daemon.pidfile
import mysql.connector
from paramiko import client
import psycopg2
from werkzeug.contrib.cache import MemcachedCache


#from unittest import result
class ssh:
    client = None
    status = None
 
    def __init__(self, address, username, password, port, timeout):
        logging.info("ssh: connecting to server: %s " % (address))
        try:
            self.client = client.SSHClient()
            self.client.set_missing_host_key_policy(client.AutoAddPolicy())
            self.client.connect(address, username=username, password=password, look_for_keys=False,timeout=timeout,port=port)
        except:
            logging.warn("ssh: can't connect to server: %s " % (address))
            self.status=False
        else:
            logging.info("ssh: connect to server: %s " % (address))
            self.status=True

 
    def sendCommand(self, command):
        if(self.client):
            stdin, stdout, stderr = self.client.exec_command(command)
            while not stdout.channel.exit_status_ready():
            # Only print data if there is data to read in the channel
                if stdout.channel.recv_ready():
                    rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                    if len(rl) > 0:
                        logging.debug("ssh: \n"+stdout.channel.recv(1024)),
            logging.info("ssh: commands has been sent, SUCCESS")
        else:
            logging.error("ssh: connection not opened")
            

class conSQL:
    
    def __init__(self):
        self.basePath = basePath      
        self.loadConf()


    def loadConf(self):
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.basePath+'/conf/ldrm.conf'))
        self.type = config.get('db','type')
        self.ip = config.get('db', 'ip')
        self.port = int(config.get('db', 'port'))
        self.dbname = config.get('db','dbname')
        self.login = config.get('db', 'login')
        self.passwd = config.get('db', 'passwd')

    def getDataFromDB(self,mac):
        if self.type == 'mysql':
            results=self.selectMySQL("""SELECT n.id as id, inet_ntoa(n.ipaddr) as ip, n.name as nodename, access, warning
                            FROM nodes as n, macs as m
                            WHERE upper(m.mac) = '%s'
                            AND n.id = m.nodeid
                            ORDER by n.id""" % (mac))
            if results is False:
                return False
            dataMac=None
            if len(results) >0:
                dataMac={"id":results[0][0],"ip":results[0][1],"nodename":results[0][2],"access":results[0][3],"warning":results[0][4]}
                results=self.selectMySQL("""SELECT CONCAT(ROUND(COALESCE(x.upceil, y.upceil, z.upceil)),'k','/', ROUND(COALESCE(x.downceil, y.downceil, z.downceil)),'k') AS mrt
                            FROM (
                                SELECT n.id, MIN(n.name) AS name, SUM(t.downceil/o.cnt) AS downceil, SUM(t.upceil/o.cnt) AS upceil
                                FROM nodeassignments na
                                JOIN assignments a ON (na.assignmentid = a.id)
                                 JOIN tariffs t ON (a.tariffid = t.id)
                                JOIN nodes n ON (na.nodeid = n.id)
                                JOIN macs m ON (m.nodeid = n.id)
                                JOIN (
                                SELECT assignmentid, COUNT(*) AS cnt
                                    FROM nodeassignments
                                    GROUP BY assignmentid
                                ) o ON (o.assignmentid = na.assignmentid)
                                WHERE (a.datefrom <= unix_timestamp() OR a.datefrom = 0)
                                AND (a.dateto > unix_timestamp() OR a.dateto = 0)
                                AND upper(m.mac) = '%s'
                                GROUP BY n.id
                            ) x
                            LEFT JOIN (
                                SELECT SUM(t.downceil)/o.cnt AS downceil,
                                SUM(t.upceil)/o.cnt AS upceil
                                FROM assignments a
                                JOIN tariffs t ON (a.tariffid = t.id)
                                JOIN nodes n ON (a.customerid = n.ownerid)
                                JOIN macs m ON (m.nodeid = n.id)
                                JOIN (
                                SELECT COUNT(*) AS cnt, ownerid FROM vnodes
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM nodeassignments, assignments a
                                    WHERE assignmentid = a.id AND nodeid = vnodes.id
                                    AND  (a.dateto > unix_timestamp() OR a.dateto = 0))
                                    GROUP BY ownerid
                                ) o ON (o.ownerid = n.ownerid)
                                WHERE (a.datefrom <= unix_timestamp() OR a.datefrom = 0)
                                AND (a.dateto > unix_timestamp() OR a.dateto = 0)
                                    AND NOT EXISTS (SELECT 1 FROM nodeassignments WHERE assignmentid = a.id)
                                    AND upper(m.mac) = '%s'
                                GROUP BY n.id
                            ) y ON (1=1)
                            RIGHT JOIN (
                                SELECT n.id, n.name, 64 AS downceil, 64 AS upceil
                                    FROM nodes as n,macs as m
                                    WHERE upper(m.mac) = '%s'
                                    AND m.nodeid = n.id
                            ) z ON (1=1)""" % (mac,mac,mac))
                if results is False:
                    return False
                if len(results) >0:
                    dataMac.update({"mrt":results[0][0]})
                else:
                    logging.warn("conSQL: can't find tariff for %s" % (mac))
            else:
                logging.warn("conSQL: wrong mac address: %s, don't exist in DB" % (mac))
            return dataMac
        elif self.type == 'pgsql':
            results=self.selectPG("""SELECT n.id as id, inet_ntoa(n.ipaddr) as ip, n.name as nodename, access, warning
                            FROM nodes as n, macs as m
                            WHERE upper(m.mac) = '%s'
                            AND n.id = m.nodeid
                            ORDER by n.id""" % (mac))
            if results is False:
                return False
            dataMac=None
            if len(results) >0:
                dataMac={"id":results[0][0],"ip":results[0][1],"nodename":results[0][2],"access":results[0][3],"warning":results[0][4]}
                results=self.selectPG("""SELECT CONCAT(ROUND(COALESCE(x.upceil, y.upceil, z.upceil)),'k','/', ROUND(COALESCE(x.downceil, y.downceil, z.downceil)),'k') AS mrt
                            FROM (
                                SELECT n.id, MIN(n.name) AS name, SUM(t.downceil/o.cnt) AS downceil, SUM(t.upceil/o.cnt) AS upceil
                                FROM nodeassignments na
                                JOIN assignments a ON (na.assignmentid = a.id)
                                 JOIN tariffs t ON (a.tariffid = t.id)
                                JOIN nodes n ON (na.nodeid = n.id)
                                JOIN macs m ON (m.nodeid = n.id)
                                JOIN (
                                SELECT assignmentid, COUNT(*) AS cnt
                                    FROM nodeassignments
                                    GROUP BY assignmentid
                                ) o ON (o.assignmentid = na.assignmentid)
                                WHERE (a.datefrom <= extract(epoch from now()) OR a.datefrom = 0)
                                AND (a.dateto > extract(epoch from now()) OR a.dateto = 0)
                                AND upper(m.mac) = '%s'
                                GROUP BY n.id
                            ) x
                            LEFT JOIN (
                                SELECT SUM(t.downceil)/o.cnt AS downceil,
                                SUM(t.upceil)/o.cnt AS upceil
                                FROM assignments a
                                JOIN tariffs t ON (a.tariffid = t.id)
                                JOIN nodes n ON (a.customerid = n.ownerid)
                                JOIN macs m ON (m.nodeid = n.id)
                                JOIN (
                                SELECT COUNT(*) AS cnt, ownerid FROM vnodes
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM nodeassignments, assignments a
                                    WHERE assignmentid = a.id AND nodeid = vnodes.id
                                    AND  (a.dateto > extract(epoch from now()) OR a.dateto = 0))
                                    GROUP BY ownerid
                                ) o ON (o.ownerid = n.ownerid)
                                WHERE (a.datefrom <= extract(epoch from now()) OR a.datefrom = 0)
                                AND (a.dateto > extract(epoch from now()) OR a.dateto = 0)
                                    AND NOT EXISTS (SELECT 1 FROM nodeassignments WHERE assignmentid = a.id)
                                    AND upper(m.mac) = '%s'
                                GROUP BY n.id, o.cnt
                            ) y ON (1=1)
                            RIGHT JOIN (
                                SELECT n.id, n.name, 64 AS downceil, 64 AS upceil
                                    FROM nodes as n,macs as m
                                    WHERE upper(m.mac) = '%s'
                                    AND m.nodeid = n.id
                            ) z ON (1=1)""" % (mac,mac,mac))

                if results is False:
                    return False
                if len(results) >0:
                    dataMac.update({"mrt":results[0][0]})
                else:
                    logging.warn("conSQL: can't find tariff for %s" % (mac))
            else:
                logging.warn("conSQL: wrong mac address: %s, don't exist in DB" % (mac))
            return dataMac
        else:
            logging.error("conSQL: wrong type of db: %s, supported only mysql or pgslq" % (self.type))

    def selectMySQL(self,query):
        try:
            cnx = mysql.connector.connect(host=self.ip,database=self.dbname,user=self.login, password=self.passwd)
            try:
                cursor = cnx.cursor()
                cursor.execute(query)
            except:
                raise
            else:
                results=cursor.fetchall()
                return results
            finally:
                cnx.close()
        except Exception as e:
            logging.error('conSQL: '+ str(e))
            return False

    def selectPG(self,query):
        try:
            con=psycopg2.connect(host=self.ip, dbname=self.dbname, user=self.login, password=self.passwd)
        except Exception as e:
            logging.error('conSQL: '+ str(e))
            return False
        else:
            cur = con.cursor()
            try:
                cur.execute(query)
            except Exception as e:
                logging.error('conSQL: '+ str(e))
                return False
            else:
                results = cur.fetchall()
                return results
            finally:
                con.close()

class queueDrd:
    
    queueDrd = deque([])
    
    dataClient={}
    
    size=1000
    
    def getAllItemInQueue(self):
        return list(self.queueDrd)
    
    def fetch(self):
        if len(self.queueDrd)>0:            
            machash=self.queueDrd.popleft()
            data=self.dataClient.pop(machash)
            return [machash,data]
        else:
            return None
    
    def add(self, machash,data):
        if len(self.queueDrd)<self.size:
            if machash not in self.queueDrd:
                self.queueDrd.append(machash)
                self.dataClient.update({machash:data})
     
    def remove(self, machash):
        if machash in self.queueDrd:
            self.queueDrd.remove(machash)
        if machash in self.dataClient:
            del self.dataClient[machash]
            
     
class deamonMT(threading.Thread):
        
    def __init__(self, QH):  
        threading.Thread.__init__(self)
        self.setDaemon(True)
        
        self.basePath = basePath      
        self.loadConf()
        
        self.cache = MemcachedCache([self.ip+':'+self.port])        
        
        self.QH = QH
        
        self.SQL=conSQL()
        
    def run(self):
        logging.info("deamonMT: ready and waiting")
        while True:
            data=self.QH.fetch()
            if data is not None:
                if self.is_valid_ipv4_address(data[1]['Framed_IP_Address']):
                    self.macData=self.cache.get(hashlib.sha1(data[0]+data[1]['Framed_IP_Address']).hexdigest())
                    if self.macData is None:
                        logging.info('deamonMT: miss cache for mac: %s ip: %s, extracting data from DB' % (data[1]['User_Name'],data[1]['Framed_IP_Address']))
                        while True:
                            dataSQL=self.SQL.getDataFromDB(data[1]['User_Name'])
                            if dataSQL is False:
                                time.sleep(5)
                            else:
                                if dataSQL is not None:
                                    data[1].update({"nodeId":dataSQL["id"]})
                                    data[1].update({"access":dataSQL["access"]})
                                    data[1].update({"warning":dataSQL["warning"]})
                                    data[1].update({"nodename":dataSQL["nodename"]})
                                    data[1].update({"mrt":dataSQL["mrt"]})
                                    self.cache.set(hashlib.sha1(data[0]+data[1]['Framed_IP_Address']).hexdigest(), data[1], timeout=self.time)
                                    self.macData=data[1]
                                else:
                                    # cant find mac in db, send info?
                                    data[1].update({"nodeId":None})
                                    self.cache.set(hashlib.sha1(data[0]+data[1]['Framed_IP_Address']).hexdigest(), data[1], timeout=self.time)
                                    self.macData=data[1]
                                    pass
                                break
                    else:
                        logging.info('deamonMT: hit cache for mac: %s ip: %s, extracting data from memcached' % (data[1]['User_Name'],data[1]['Framed_IP_Address']))
                    execOnMT=None
                    logging.debug(self.macData)                                    
                    if self.macData['nodeId'] is not None and self.macData['nodename'] is not None and  self.macData['mrt'] is not None and self.is_valid_ipv4_address(self.macData['Framed_IP_Address']) and self.is_valid_ipv4_address(self.macData['NAS_IP_Address']):
                        execOnMT = """/queue simple remove [find comment="""+str(self.macData['nodeId'])+"""]
/ip firewall address-list remove [find comment="""+str(self.macData['nodeId'])+"""]
/ip firewall nat remove [find comment="""+str(self.macData['nodeId'])+"""]
/queue simple add name="""+str(self.macData['nodename'])+""" target="""+str(self.macData['Framed_IP_Address'])+"""/32 parent=none packet-marks="" priority=8/8 queue=s100/s100 limit-at=64k/64k max-limit="""+str(self.macData['mrt'])+""" burst-limit=0/0 burst-threshold=0/0 burst-time=0s/0s comment="""+str(self.macData['nodeId'])
    
                        if self.macData['access'] == 0:
                            execOnMT +="""\n/ip firewall address-list add list=blacklist address="""+str(self.macData['Framed_IP_Address'])+""" comment="""+str(self.macData['nodeId'])
                            if self.macData['warning']  == 1:
                                execOnMT += """\n/ip firewall nat add chain=warn action=dst-nat to-addresses="""+self.lmswarn+""" to-ports=8001 protocol=tcp src-address="""+str(self.macData['Framed_IP_Address'])+""" limit=10/1h,1:packet log=no log-prefix="" comment="""+str(self.macData['nodeId'])
                        if self.macData['access'] == 1:  
                            if self.macData['warning'] == 1:
                                execOnMT += """\n/ip firewall nat add chain=warn action=dst-nat to-addresses="""+self.lmswarn+""" to-ports=8001 protocol=tcp src-address="""+str(self.macData['Framed_IP_Address'])+""" limit=10/1h,1:packet log=no log-prefix="" comment="""+str(self.macData['nodeId'])
                        
                        logging.info("deamonMT: commands are ready to send to Mikrotik:\n"+execOnMT)
                        if self.api == 'ssh':
                            self.executeMT(execOnMT,self.macData['NAS_IP_Address'])
                        else:
                            logging.error('deamonMT: incorrect api: %s' % (self.api))
                    else:
                        logging.info('deamonMT: incorrect data: nodeId, access, warning, nodename, mtr, NAS_IP_Address or Framed_IP_Address')
                else:
                    logging.info('deamonMT: incorrect ip or null: Framed_IP_Address')
            else:
                time.sleep(1)
     
    def is_valid_ipv4_address(self,address):
        try:
            socket.inet_pton(socket.AF_INET, address)
        except AttributeError:  # no inet_pton here, sorry
            try:
                socket.inet_aton(address)
            except socket.error:
                return False
            return address.count('.') == 3
        except socket.error:  # not a valid address
            return False
    
        return True
                    
    def loadConf(self):
        
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.basePath+'/conf/ldrm.conf'))
        
        self.ip = config.get('memcached', 'ip')
        self.port = config.get('memcached', 'port')
        self.time = int(config.get('memcached', 'time'))
        
        self.lmswarn = config.get('lms', 'warnserver')
        
        self.api = config.get('mt', 'api')
        self.loginSsh = config.get('mt', 'login')
        self.passwdSsh = config.get('mt', 'pass')
        self.portSsh = int(config.get('mt', 'port'))
        self.timeoutSsh = int(config.get('mt', 'timeout'))
        
    def executeMT(self,execOnMT,ipToCon):        
        while (True):
            S=ssh(ipToCon,self.loginSsh, self.passwdSsh, int(self.portSsh), int(self.timeoutSsh))
            if S.status is True:
                S.sendCommand(execOnMT)
                S.client.close()
                break
            else:
                time.sleep(5)

class servertcp(threading.Thread):
        
    def __init__(self, QH):  
        threading.Thread.__init__(self)
        self.setDaemon(True)
        
        self.basePath = basePath      
        self.loadConf()        
        
        self.QH = QH
        
    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.host, int(self.port)))
        s.listen(5)
        logging.info("servertcp: ready and waiting on port %s" % (self.port))
        while True:
            client, ipPort = s.accept()
            client.settimeout(int(self.connectionTimeout))
            if ipPort[0] == '127.0.0.1':
                try:
                    data = json.loads(client.recv(1024))
                    if data[0] == 'DATA':
                        self.QH.add(data[1],data[2])
                        client.send(json.dumps(['OK']))
                        logging.info("servertcp: new data, mac: %s from %s" % (data[2]['User_Name'],ipPort[0]))
                    else:
                        client.send(json.dumps(['BADCOMMAND']))
                    client.close    
                except ValueError as e:
                    logging.warn('servertcp: recived data is not json, %s' % (e))
                    client.close
                except socket.timeout as e:
                    logging.warn('servertcp: connection Timeout, %s' % (e))
                    client.close
            else:
                logging.warn("servertcp: dont't accept conections form %s, only localhost is accepted" % (ipPort[0]))
                client.close
            
    def loadConf(self):
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.basePath+'/conf/ldrm.conf'))
        self.host = config.get('tcpserver', 'host')
        self.port = config.get('tcpserver', 'port')
        self.connectionTimeout = config.get('tcpserver', 'connectionTimeout')
        
class drdDaemon:
        
    def __init__(self, basePath):
        self.basePath = basePath
        self.loadConf()
    
    def run(self):
        if self.log=='debug':
            logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
            logging.getLogger("paramiko").setLevel(logging.DEBUG)
        elif self.log=='info':
            logging.basicConfig(level=logging.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')
            logging.getLogger("paramiko").setLevel(logging.INFO)
        elif self.log=='warn':
            logging.basicConfig(level=logging.WARN, format='%(relativeCreated)6d %(threadName)s %(message)s')
            logging.getLogger("paramiko").setLevel(logging.WARN)
        elif self.log=='error':
            logging.basicConfig(level=logging.ERROR, format='%(relativeCreated)6d %(threadName)s %(message)s')
            logging.getLogger("paramiko").setLevel(logging.ERROR)
        elif self.log=='critical':
            logging.basicConfig(level=logging.CRITICAL, format='%(relativeCreated)6d %(threadName)s %(message)s')
            logging.getLogger("paramiko").setLevel(logging.CRITICAL)
        else:
            logging.basicConfig(level=logging.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')
            logging.getLogger("paramiko").setLevel(logging.INFO)
        
        
#         logging.basicConfig(level=logging.DEBUG, 
#                             format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
#                             datefmt='%d-%m-%d %H:%M',
#                             filename='log/drd.log',
#                             filemode='w')

        logging.info("drdDaemon: start main thread")

        QH=queueDrd()
        
        ST = servertcp(QH)
        ST.start()
        
        DMT = deamonMT(QH)
        DMT.start()

        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
        logging.info("drdDaemon: stop main thread")
                
    def loadConf(self):
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.basePath+'/conf/ldrm.conf'))
        self.log = config.get('main', 'log')


    def start(self):
        """
        Start the daemon
        """
        if os.path.isfile(self.basePath+'/conf/ldrm.conf') is False:
            print 'drdDaemon: Where is conf, should be in main directory\nfile: ldrm.conf'
            sys.exit(1)
        
        # Check for a pidfile to see if the daemon already runs
        #pidfile = self.basePath + '/tmp/drd.pid'
        pidfile = '/tmp/drd.pid'
        try:
            pf = file(pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if pid:
            message = "drdDaemon: pidfile %s already exist. Daemon already running?"
            sys.stderr.write(message % pidfile)
            sys.exit(1)
        
        # Start the daemon

        working_directory=self.basePath
        pidfile=daemon.pidfile.PIDLockFile(pidfile)
        if self.log is True:
            stdout = file(self.basePath + '/log/stdout.log', 'a')
            stderr = file(self.basePath + '/log/stderr.log', 'a')            
            with daemon.DaemonContext(stdout=stdout, stderr=stderr, working_directory=working_directory, pidfile=pidfile):
                self.run()
        else:
            with daemon.DaemonContext(working_directory=working_directory, pidfile=pidfile):
                self.run()

    def stop(self):
        """
        Stop the daemon
        """        
        # Get the pid from the pidfile
        #pidfile = self.basePath + '/tmp/drd.pid'
        pidfile = '/tmp/drd.pid'
        
        try:
            pf = file(pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
    
        if not pid:
            message = "pidfile %s does not exist. Daemon not running?"
            sys.stderr.write(message % pidfile)
            return  # not an error in a restart
    
        # Try killing the daemon process    
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(pidfile):
                    os.remove(pidfile)
            else:
                print str(err)
                sys.exit(1)
    
if __name__ == "__main__":
    basePath = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) == 2:
        if 'debug' == sys.argv[1]:
            drdDaemon(basePath).run()
        elif 'start' == sys.argv[1]:            
            drdDaemon(basePath).start()
        elif 'stop' == sys.argv[1]:
            drdDaemon(basePath).stop()
        elif 'help' == sys.argv[1]:
            print "usage: %s \n\tstart \t\t-> start deamon \n\tstop \t\t-> stop deamon \n\tdebug \t-> non-daemon mode \n\thelp \t-> show this" % sys.argv[0]
            sys.exit(2)
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s \n\tstart \t-> start deamon \n\tstop \t-> stop deamon \n\tdebug \t-> non-daemon mode \n\thelp \t-> show this" % sys.argv[0]
        sys.exit(2)   
