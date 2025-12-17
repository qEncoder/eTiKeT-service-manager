"""Windows service manager templates for VBS and XML generation."""

import xml.etree.ElementTree as ET
from pathlib import Path


VBS_PROC_LAUNCHER_TEMPLATE = """Option Explicit

Dim objWMI, objStartup, objFSO
Dim strPidFile, strCommand, strWorkDir
Dim intThrottleSeconds

' --- CONFIGURATION ---
strCommand = "{executable}"
strPidFile = "{pid_file}"
strWorkDir = "{working_dir}"
intThrottleSeconds = 60
' ---------------------

Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objWMI = GetObject("winmgmts:\\\\.\\root\\cimv2")

' Main restart loop - keeps process alive indefinitely
' To stop: kill the child process, then kill wscript.exe
Do While True
    Dim intReturn, intPID, colItems, objItem, strCreationDate, objFile
    
    Set objStartup = objWMI.Get("Win32_ProcessStartup").SpawnInstance_
    objStartup.ShowWindow = 0
    
    intReturn = objWMI.Get("Win32_Process").Create(strCommand, strWorkDir, objStartup, intPID)
    
    If intReturn = 0 Then
        ' Get process creation timestamp for identification
        Set colItems = objWMI.ExecQuery("SELECT CreationDate FROM Win32_Process WHERE ProcessId = " & intPID)
        strCreationDate = ""
        For Each objItem in colItems
            strCreationDate = objItem.CreationDate
        Next

        ' Write PID + Timestamp to file
        Set objFile = objFSO.CreateTextFile(strPidFile, True)
        If strCreationDate <> "" Then
            objFile.WriteLine intPID & "," & strCreationDate
        Else
            objFile.WriteLine intPID
        End If
        objFile.Close
        Set objFile = Nothing
        
        ' Monitor Loop: Keep watching while child is alive
        Do While ProcessExists(intPID)
            WScript.Sleep 200 
        Loop
        
        ' Cleanup PID file
        If objFSO.FileExists(strPidFile) Then
            objFSO.DeleteFile strPidFile
        End If
        
        ' Process exited - throttle before restart
        WScript.Sleep intThrottleSeconds * 1000
    Else
        ' Failed to start process - throttle before retry
        WScript.Sleep intThrottleSeconds * 1000
    End If
Loop

Function ProcessExists(pid)
    Dim colProcesses
    Set colProcesses = objWMI.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE ProcessId = " & pid)
    ProcessExists = (colProcesses.Count > 0)
End Function
"""


def create_scheduled_task_xml(
    service_name: str,
    version: str,
    vbs_path: Path,
    userid: str,
    user_sid: str
) -> str:
    """Generate Windows Task Scheduler XML for the service.
    
    Args:
        service_name: Name of the service.
        version: Version string for the service.
        vbs_path: Path to the VBS launcher script.
        userid: Windows user ID (e.g., DOMAIN\\username).
        user_sid: Windows user SID.
    
    Returns:
        XML string for Task Scheduler (UTF-16 encoded declaration).
    """
    root = ET.Element('Task', {
        'version': '1.3',
        'xmlns': 'http://schemas.microsoft.com/windows/2004/02/mit/task'
    })
    
    reg_info = ET.SubElement(root, 'RegistrationInfo')
    ET.SubElement(reg_info, 'Description').text = f'Service {service_name}\nversion={version}'
    ET.SubElement(reg_info, 'URI').text = f'\\\\{service_name}'
    
    triggers = ET.SubElement(root, 'Triggers')
    logon_trigger = ET.SubElement(triggers, 'LogonTrigger')
    ET.SubElement(logon_trigger, 'Enabled').text = 'true'
    ET.SubElement(logon_trigger, 'UserId').text = userid
    
    principals = ET.SubElement(root, 'Principals')
    principal = ET.SubElement(principals, 'Principal', {'id': 'Author'})
    ET.SubElement(principal, 'UserId').text = user_sid
    ET.SubElement(principal, 'LogonType').text = 'InteractiveToken'
    ET.SubElement(principal, 'RunLevel').text = 'LeastPrivilege'
    
    settings = ET.SubElement(root, 'Settings')
    ET.SubElement(settings, 'MultipleInstancesPolicy').text = 'IgnoreNew'
    ET.SubElement(settings, 'DisallowStartIfOnBatteries').text = 'false'
    ET.SubElement(settings, 'StopIfGoingOnBatteries').text = 'false'
    ET.SubElement(settings, 'AllowHardTerminate').text = 'true'
    ET.SubElement(settings, 'StartWhenAvailable').text = 'false'
    ET.SubElement(settings, 'RunOnlyIfNetworkAvailable').text = 'false'
    
    idle_settings = ET.SubElement(settings, 'IdleSettings')
    ET.SubElement(idle_settings, 'Duration').text = 'PT10M'
    ET.SubElement(idle_settings, 'WaitTimeout').text = 'PT1H'
    ET.SubElement(idle_settings, 'StopOnIdleEnd').text = 'false'
    ET.SubElement(idle_settings, 'RestartOnIdle').text = 'false'
    
    ET.SubElement(settings, 'AllowStartOnDemand').text = 'true'
    ET.SubElement(settings, 'Enabled').text = 'true'
    ET.SubElement(settings, 'Hidden').text = 'false'
    ET.SubElement(settings, 'RunOnlyIfIdle').text = 'false'
    ET.SubElement(settings, 'DisallowStartOnRemoteAppSession').text = 'false'
    ET.SubElement(settings, 'UseUnifiedSchedulingEngine').text = 'true'
    ET.SubElement(settings, 'WakeToRun').text = 'false'
    ET.SubElement(settings, 'ExecutionTimeLimit').text = 'PT0S'
    ET.SubElement(settings, 'Priority').text = '7'
    
    restart_failure = ET.SubElement(settings, 'RestartOnFailure')
    ET.SubElement(restart_failure, 'Interval').text = 'PT1M'
    ET.SubElement(restart_failure, 'Count').text = '10'
    
    actions = ET.SubElement(root, 'Actions', {'Context': 'Author'})
    exec_action = ET.SubElement(actions, 'Exec')
    ET.SubElement(exec_action, 'Command').text = 'wscript.exe'
    ET.SubElement(exec_action, 'Arguments').text = f'"{vbs_path}"'
        
    xml_str = ET.tostring(root, encoding='unicode')
    final_xml = '<?xml version="1.0" encoding="UTF-16"?>\n' + xml_str

    return final_xml
