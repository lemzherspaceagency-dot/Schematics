; ANTINODE installer.
;
; Installs a single self-contained executable, a Start Menu entry and an
; uninstaller. The game writes its save to %APPDATA%\Antinode, which the
; uninstaller offers to remove.

Unicode true
!include "MUI2.nsh"
!include "x64.nsh"

!ifndef VERSION
  !define VERSION "0.1.0"
!endif

!define APPNAME    "ANTINODE"
!define COMPANY    "ANTINODE"
!define EXENAME    "Antinode.exe"
!define REGKEY     "Software\Microsoft\Windows\CurrentVersion\Uninstall\ANTINODE"

Name              "${APPNAME} ${VERSION} alpha"
OutFile           "..\dist\ANTINODE-${VERSION}-alpha-setup.exe"
InstallDir        "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey  HKLM "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

VIProductVersion "0.1.0.0"
VIAddVersionKey  "ProductName"     "${APPNAME}"
VIAddVersionKey  "FileDescription" "${APPNAME} installer"
VIAddVersionKey  "FileVersion"     "${VERSION}"
VIAddVersionKey  "ProductVersion"  "${VERSION}"
VIAddVersionKey  "LegalCopyright"  ""

!define MUI_ICON   "antinode.ico"
!define MUI_UNICON "antinode.ico"
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXENAME}"
!define MUI_FINISHPAGE_RUN_TEXT "Enter the Vault"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Function .onInit
    ${IfNot} ${RunningX64}
        MessageBox MB_OK|MB_ICONSTOP "ANTINODE needs 64-bit Windows."
        Abort
    ${EndIf}
FunctionEnd

Section "ANTINODE" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "..\dist\${EXENAME}"
    File "/oname=README.txt" "..\README.md"
    File "/oname=LICENSE.txt" "..\LICENSE"

    WriteRegStr HKLM "Software\${APPNAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\${APPNAME}" "Version"    "${VERSION}"

    ; Add/Remove Programs entry
    WriteRegStr   HKLM "${REGKEY}" "DisplayName"     "${APPNAME} ${VERSION} alpha"
    WriteRegStr   HKLM "${REGKEY}" "DisplayIcon"     "$INSTDIR\${EXENAME}"
    WriteRegStr   HKLM "${REGKEY}" "DisplayVersion"  "${VERSION}"
    WriteRegStr   HKLM "${REGKEY}" "Publisher"       "${COMPANY}"
    WriteRegStr   HKLM "${REGKEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr   HKLM "${REGKEY}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKLM "${REGKEY}" "NoModify" 1
    WriteRegDWORD HKLM "${REGKEY}" "NoRepair" 1

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut  "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"   "$INSTDIR\${EXENAME}"
    CreateShortcut  "$SMPROGRAMS\${APPNAME}\Uninstall.lnk"    "$INSTDIR\uninstall.exe"

    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Desktop shortcut" SecDesktop
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${EXENAME}"
SectionEnd

LangString DESC_SecMain    ${LANG_ENGLISH} "The game. One self-contained executable, no extra runtime needed."
LangString DESC_SecDesktop ${LANG_ENGLISH} "Put a shortcut on the desktop."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}    $(DESC_SecMain)
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_SecDesktop)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
    Delete "$INSTDIR\${EXENAME}"
    Delete "$INSTDIR\README.txt"
    Delete "$INSTDIR\LICENSE.txt"
    Delete "$INSTDIR\uninstall.exe"
    RMDir  "$INSTDIR"

    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Uninstall.lnk"
    RMDir  "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"

    DeleteRegKey HKLM "${REGKEY}"
    DeleteRegKey HKLM "Software\${APPNAME}"

    ; Saved vaults live outside the install directory, so ask before removing.
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Remove your saved vault as well?" IDNO keep_saves
        Delete "$APPDATA\Antinode\chamber.antinode"
        RMDir  "$APPDATA\Antinode"
    keep_saves:
SectionEnd
