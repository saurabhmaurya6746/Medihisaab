Option Explicit

Dim shell, fso, appDir, launcher, exitCode, errFile, logDir, logFile, errReason, localAppData, ts

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(appDir, "start-pharmacy.bat")
shell.CurrentDirectory = appDir

localAppData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
If localAppData = "" Or localAppData = "%LOCALAPPDATA%" Then
    localAppData = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\AppData\Local"
End If

logDir = fso.BuildPath(localAppData, "PharmacyApp\logs")
If Not fso.FolderExists(fso.BuildPath(localAppData, "PharmacyApp")) Then
    On Error Resume Next
    fso.CreateFolder fso.BuildPath(localAppData, "PharmacyApp")
    On Error GoTo 0
End If
If Not fso.FolderExists(logDir) Then
    On Error Resume Next
    fso.CreateFolder logDir
    On Error GoTo 0
End If

errFile = fso.BuildPath(logDir, "launcher-error.txt")
logFile = fso.BuildPath(logDir, "launcher.log")

If Not fso.FileExists(launcher) Then
    MsgBox "MediHisaab launcher was not found at:" & vbCrLf & launcher & vbCrLf & vbCrLf & _
           "Please repair or reinstall MediHisaab.", vbCritical, "MediHisaab Launcher Error"
    WScript.Quit 1
End If

' Clear prior error marker
If fso.FileExists(errFile) Then
    On Error Resume Next
    fso.DeleteFile errFile, True
    On Error GoTo 0
End If

' Run start-pharmacy.bat silently with window style 0 and wait for completion
exitCode = shell.Run("cmd.exe /c """"" & launcher & """ >> """ & logFile & """ 2>&1""", 0, True)

If exitCode <> 0 Then
    errReason = ""
    If fso.FileExists(errFile) Then
        On Error Resume Next
        Set ts = fso.OpenTextFile(errFile, 1, False)
        If Not ts.AtEndOfStream Then
            errReason = ts.ReadAll()
        End If
        ts.Close
        On Error GoTo 0
    End If

    If Trim(errReason) = "" Then
        errReason = "Startup failed with exit code " & exitCode & "."
    End If

    MsgBox "MediHisaab could not start." & vbCrLf & vbCrLf & _
           Trim(errReason) & vbCrLf & vbCrLf & _
           "Diagnostic log file:" & vbCrLf & logFile, _
           vbCritical, "MediHisaab Startup Failure"
End If

WScript.Quit exitCode
