Option Explicit

Dim shell, fso, appDir, launcher, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(appDir, "start-pharmacy.bat")
shell.CurrentDirectory = appDir

If Not fso.FileExists(launcher) Then
    MsgBox "MediHisaab launcher was not found. Repair or reinstall the application.", vbCritical, "MediHisaab"
    WScript.Quit 1
End If

' Run the existing startup flow without showing its Command Prompt window.
exitCode = shell.Run("""" & launcher & """", 0, True)
If exitCode <> 0 Then
    MsgBox "MediHisaab could not start. Repair or reinstall the application, then try again.", vbExclamation, "MediHisaab"
End If

WScript.Quit exitCode
