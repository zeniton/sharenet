#!/usr/bin/python

import ConfigParser
import sys
import os
import subprocess
import logging
import shutil
import glob
import MySQLdb
import hed
import dn
from importexception import *

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

config = ConfigParser.ConfigParser()
config.readfp(open("sharenet.ini"))
binDir = config.get("Import", "bin")
inDir = config.get("Import", "in")
workDir = config.get("Import", "work")
doneDir = config.get("Import", "done")
dbHost = config.get("Database", "host")
dbName = config.get("Database", "name")
dbUser = config.get("Database", "uid")
dbPwd = config.get("Database", "pwd")

def cleanWorkDir():
	for f in glob.glob(os.path.join(workDir, "*")):
		os.unlink(f)

#Sanity check
files = glob.glob(os.path.join(inDir, "*.lzh"))
if (len(files) == 0):
	logging.info("Nothing to import.")
	sys.exit(0)
else:
	files.sort()
	
#Connect to database
try:
	logging.info("Connecting to database...")
	db = MySQLdb.connect(host=dbHost, user=dbUser, passwd=dbPwd, db=dbName)
	logging.info("Database connected")
except:
	logging.error("Cannot connect to database")
	sys.exit(1)

#Setup extraction app
lha = os.path.join(binDir, "lha")
if os.name == "nt":
	extract = [lha, "e", ""]
elif os.name == "posix":
	extract = [lha, "xq2f", ""]	#eXtract, really Quiet, Force
logging.debug(lha)

try:
	os.chdir(workDir)
	cleanup = db.cursor()
	for lzh in files:
		logging.debug(lzh)

		#Check if downloaded file is empty
		statinfo = os.stat(lzh)
		if statinfo.st_size == 0L:
			raise ImportError(fileName + " is empty")

		#Check if downloaded file has been imported
		cursor = db.cursor()
		(filePath, fileName) = os.path.split(lzh)
		sql = "call isFileImported('%s')" % fileName
		logging.debug(sql)
		cursor.execute(sql)
		result = cursor.fetchone()
		done = (result[0] != 0)
		cursor.close()
		if done:
			logging.warning(fileName + " is already imported")
			shutil.move(lzh, os.path.join(doneDir, fileName))
			continue

		logging.info("Importing " + fileName)
		try:
			cleanWorkDir()
			extract[2] = lzh
			logging.debug(extract)
			subprocess.call(extract)
			for f in glob.glob(os.path.join(workDir, "*.hed")):
				logging.debug(f)
				hed.parse(f, db)
			for f in glob.glob(os.path.join(workDir, "*.DN")):
				logging.debug(f)
				dn.parse(f, db)
			shutil.move(lzh, os.path.join(doneDir, fileName))
			cleanup.execute("call addFile('%s')" % fileName)
			cleanup.execute("call importClosing()")
			db.commit()
			logging.info(fileName + " imported")
		except ImportWarning, e:
			logging.error(e.msg)
			break
		except ImportError, e:
			logging.error(e.msg)
			raise
		except:
			logging.error(sys.exc_info()[0])
			db.rollback()
			raise
	logging.info("Import done.")
finally:
	db.close()
	cleanWorkDir()
