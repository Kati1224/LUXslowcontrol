import Tkinter
from Tkinter import *
import threading
import time
import datetime
import scriptstuff
import sys
import math
import random
import KrGUI
import ThermosyphonScripts
import ShutdownScript
import constuff
import flaglist
import scipy

#This class is passed to all functions and gives them all shared information
class AutoKrParams():
    def __init__(self):
        self.rindex = constuff.conclass.newcon()
        self.windex = constuff.conclass.newcon(1)
        self.script = None
        self.status = "Parameters Set"
        self.GUItitle = "Automated Processing"
        self.key = constuff.readID(self.rindex)
    
        ### set additional parameters ###
        self.pauselength = 10  
        self.SampleDelayTime = 3*60   # sampling time         
        self.TransitionTime = 2*60     # Transition,
        self.SRSBaseline = 10*60       # Time for RGA baseline to stabilize
        self.DurXeFeed = 10*60          # Xe feed duration
        self.DurXeRecovery = 4*60*60   # Xe Recovery duration
        self.XeFeedRate = [20]   # MFC2 flow rate
        ### Vd04 0 is open, 1 is closed.
        
# The actual script part
# Including fluff bypasses a bug in threading.Thread
def AutoKrScript(fluff,Params):
    flaglist.flags.scriptflag.set()
    flaglist.flags.auxflag.append([threading.Event(),threading.Event()])
    # These lines check the status of abort flag and if it is thrown will 
    # escape from the script   
    if not scriptstuff.sleepaware(Params,scriptstuff.empty):
        return 0
    # Confirms that the system is in the shutdown state
    ShutdownScript.KrShutdown()
    if not scriptstuff.sleepaware(Params,scriptstuff.empty,Params.pauselength):
        return 0
    # Sets the status variable to be read by the GUI 
    Params.status = "Starting up"
    print Params.status

    # Start of the script for x number of microcycles
    for x in range(len(Params.XeFeedRate)):
        # He charge Phase
        Params.status = "Beginning He Charge"
        print Params.status
        tnaught = time.time()
        # Set the conditions to begin He gas flow
        scriptstuff.setvalue(Params.windex,Params.key,"P1",0)
        scriptstuff.setvalue(Params.windex,Params.key,"MFC1",60,"SP1")
        scriptstuff.setvalue(Params.windex,Params.key,"P1",30,"SP1")
        scriptstuff.setvalue(Params.windex,Params.key,"P2",0)
        scriptstuff.setvalue(Params.windex,Params.key,"P2",1,"NC1")
        scriptstuff.setvalue(Params.windex,Params.key,"VD04",1)
        scriptstuff.setvalue(Params.windex,Params.key,"VD05",0)
        scriptstuff.setvalue(Params.windex,Params.key,"VD03",0)

        # Check pressure condition of Charcoal Column
        p_cc_0 = scriptstuff.readvalue(Params.windex,Params.key,"PT20")
        Params.status = "Pressure at PT20: {0:3.1f}".format(p_cc_0)
        p_cc_target = 500.0

        # Begin He charging of the Charcoal Column, conditional based on 
        # achieving a pressure of 500 mbar in the column 
        scriptstuff.setvalue(Params.windex,Params.key,"VD06",1)
        scriptstuff.setvalue(Params.windex,Params.key,"P1",1)

        p_cc_value = scriptstuff.readvalue(Params.windex,Params.key,"PT20")
        while p_cc_value < p_cc_target:
            Params.status = ("He Charge proceeding, " +
                             "current pressure is {0:5.1f}").format(p_cc_value)
            p_cc_value = scriptstuff.readvalue(Params.windex,Params.key,"PT20")
            if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                          Params.pauselength):
                return 0

        # Shutoff flow of He but wait and observe pressure in column 
        scriptstuff.setvalue(Params.windex,Params.key,"VD06",0)
        Params.status = "Waiting while CC pressure stabilizes..."
        if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                      60,time.time()):
            return 0

        # Set He circulation parameters
        scriptstuff.setvalue(Params.windex,Params.key,"VD05",1)
        scriptstuff.setvalue(Params.windex,Params.key,"MFC1",200,"SP1")
        scriptstuff.setvalue(Params.windex,Params.key,"P1",60,"SP1")
        time.sleep(Params.pauselength)
        scriptstuff.setvalue(Params.windex,Params.key,"VD03",1)
        time.sleep(Params.pauselength)
        scriptstuff.setvalue(Params.windex,Params.key,"P2",1)

        # Read final pressure and duration
        p_cc_value = scriptstuff.readvalue(Params.windex,Params.key,"PT20")
        t_he_charge_end = time.time() - tnaught
        Params.status = ("He Charge complete, final value {0:.1f} and " +
                         "duration {1} sec").format(p_cc_value,t_he_charge_end)
        print Params.status

        if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                      Params.pauselength,time.time()):
            return 0 

        # Wait for RGA baseline to stabilize
        Params.status = ("Waiting for SRS Baseline to stabilize")
        print Params.status
        if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                      Params.SRSBaseline,time.time()):
            return 0
        
        # Begin Xe feed
        Params.status = ("Begin Xe Feed of " +
                        "{0:.1f} SLPM".format(Params.XeFeedRate[x]))
        print Params.status
        scriptstuff.setvalue(Params.windex,Params.key,"VD09",1)
        scriptstuff.setvalue(Params.windex,Params.key,"MFC2",
                             Params.XeFeedRate[x],"SP1")
        t0 = time.time()
        
        #Output date and time to process log
        now = datetime.datetime.now()
        LogFile = open('/SVN/DAQ/SCGUI/KrRemoval/log/process_log.txt','a')
        logstring = "Xe feed begins: {0}\n".format(now)
        LogFile.write(logstring)
        LogFile.close()

        # Wait for DurXeFeed to pass, then end feed
        if not scriptstuff.sleepaware(Params,
                                ShutdownScript.KrShutdown,Params.DurXeFeed,t0):
            return 0
        scriptstuff.setvalue(Params.windex,Params.key,"MFC2",0,"SP1")
        scriptstuff.setvalue(Params.windex,Params.key,"VD09",0)

        # Begin Chromatography phase, and look at SRS average
        Params.status = ("Chromatography of Microcycle: " +
                          "Establishing RGA baseline")
        print Params.status
        baseline = []
        t_baseline = time.time() + (20*60)   # time to establish baseline
        while time.time() < t_baseline:
            baseline.append(scriptstuff.readvalue(Params.rindex,
                            Params.key,"SRS","XE134"))
            if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                          5,time.time()):
                return 0
        
        baseline_avg = scipy.mean(baseline)
        baseline_stdev = scipy.std(baseline)
        
        # Look for running average to exceed 5 std devs above baseline
        Params.status = "Chromatography of Microcycle: Waiting for Xenon"
        print Params.status
        # First, populate a list for 5 minutes
        running_list = []
        while len(running_list) < 60:
            running_list.append(scriptstuff.readvalue(Params.rindex,
                            Params.key,"SRS","XE134"))
            if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                          5,time.time()):
                return 0
        running_avg = scipy.mean(running_list)
        # Now, look for the running average to exceed baseline
        while running_avg < (baseline_avg + 5.0*baseline_stdev):
            running_list.append(scriptstuff.readvalue(Params.rindex,
                                                  Params.key,"SRS","XE134"))
            running_avg = scipy.mean(running_list[-60:])
            if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                          5,time.time()):
                return 0
        
        # When threshold has been exceed, trigger recovery
        Params.status=("Xenon exiting column, starting recovery")
        print Params.status
        # Output start time of Xe recovery to log file
        now = datetime.datetime.now()
        LogFile = open('/SVN/DAQ/SCGUI/KrRemoval/log/process_log.txt','a')
        logstring = "Xe recovery begins: {0}\n".format(now)
        LogFile.write(logstring)
        LogFile.close()
        # Set parameters for recovery
        scriptstuff.setvalue(Params.windex,Params.key,"P2",0)
        scriptstuff.setvalue(Params.windex,Params.key,"P1",0)
        scriptstuff.setvalue(Params.windex,Params.key,"P1",60,"SP1")
        scriptstuff.setvalue(Params.windex,Params.key,"P2",0,"NC1")
        time.sleep(30)
        scriptstuff.setvalue(Params.windex,Params.key,"VD04",0)
        scriptstuff.setvalue(Params.windex,Params.key,"VD05",0)
        scriptstuff.setvalue(Params.windex,Params.key,"VD06",1)
        scriptstuff.setvalue(Params.windex,Params.key,"VD03",0)
        scriptstuff.setvalue(Params.windex,Params.key,"MFC1",20,"SP1")
        Params.status="Transition to XeRecovery of microcycle " + str(x+1)
        time.sleep(Params.TransitionTime)
        scriptstuff.setvalue(Params.windex,Params.key,"P2",1)     
        Params.status="Evacuating column"
        time.sleep(Params.TransitionTime)
        scriptstuff.setvalue(Params.windex,Params.key,"P3",1)
        scriptstuff.setvalue(Params.windex,Params.key,"P1",1)
        Params.status="XeRecovery of microcycle " + str(x+1)
        print Params.status
        
		# Wait and then take a sample
        time.sleep(Params.SampleDelayTime)
        scriptstuff.setvalue(Params.windex,Params.key,"VD07",1)    
        time.sleep(Params.SampleDelayTime)
        scriptstuff.setvalue(Params.windex,Params.key,"VD07",0)
        
        # Wait for recovery to complete, then shutdown system
        if not scriptstuff.sleepaware(Params,ShutdownScript.KrShutdown,
                                      Params.DurXeRecovery,time.time()):
            return 0
        scriptstuff.setvalue(Params.windex,Params.key,"P3",0)
        scriptstuff.setvalue(Params.windex,Params.key,"P1",0)
        scriptstuff.setvalue(Params.windex,Params.key,"VD06",0)    
        time.sleep(Params.pauselength)
        scriptstuff.setvalue(Params.windex,Params.key,"P2",0)
        time.sleep(Params.pauselength)
        scriptstuff.setvalue(Params.windex,Params.key,"VD04",1)
        scriptstuff.setvalue(Params.windex,Params.key,"MFC1",0,"SP1")
        time.sleep(Params.pauselength)
        # If the xenon source pressure is too low, end the script
        supplypressure = scriptstuff.readvalue(Params.windex,Params.key,"PT14") 
        if supplypressure < 10:
            break
        
    flaglist.flags.scriptflag.clear()    
    
# Intializes the parameter class, the script and the GUI
# fluffstring bypasses a bug in threading.Thread (its passed but not used)

def RunAutoKr():
    if flaglist.flags.scriptflag.is_set():
        print "script running, wait until it ends or abort to run a new one"
        return 0
    
    if flaglist.flags.readonlyflag.is_set():
        print ("You are in read-only mode, log in as a read/write user,"
                " or boot the current user from the main navigation window")
        return 0
        
        
    P = AutoKrParams()
    P.script = threading.Thread(target=AutoKrScript,args=("fluff",P))
    P.script.daemon = True
    P.script.start()
    scriptstuff.ScriptGUI(P)




