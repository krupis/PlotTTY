// Portable Windows entry point. The application and its DLLs stay in app/.
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static int fail(DWORD error)
{
    wchar_t message[512];
    swprintf_s(message, 512,
        L"Could not start PlotTTY (Windows error %lu).\n\n"
        L"Extract the entire ZIP and keep the app folder beside PlotTTY.exe.", error);
    MessageBoxW(NULL, message, L"PlotTTY", MB_OK | MB_ICONERROR);
    return 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show)
{
    wchar_t directory[32768], executable[32768], command[32768];
    DWORD length = GetModuleFileNameW(NULL, directory, 32768);
    if (!length || length >= 32768)
        return fail(ERROR_INSUFFICIENT_BUFFER);
    wchar_t *separator = wcsrchr(directory, L'\\');
    if (!separator)
        return fail(ERROR_BAD_PATHNAME);
    *separator = L'\0';
    if (wcslen(directory) + wcslen(L"\\app\\PlotTTY.exe") >= 32768 ||
        wcslen(directory) + wcslen(L"\\app\\PlotTTY.exe") + wcslen(arguments) + 4 >= 32768)
        return fail(ERROR_INSUFFICIENT_BUFFER);
    if (swprintf_s(executable, 32768, L"%ls\\app\\PlotTTY.exe", directory) < 0 ||
        swprintf_s(command, 32768, L"\"%ls\" %ls", executable, arguments) < 0)
        return fail(ERROR_INSUFFICIENT_BUFFER);

    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = (WORD)show;
    // Set the working directory explicitly so profiles/logs stay beside the launcher.
    if (!CreateProcessW(executable, command, NULL, NULL, FALSE, 0, NULL,
                        directory, &startup, &process))
        return fail(GetLastError());
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD result = 1;
    GetExitCodeProcess(process.hProcess, &result);
    CloseHandle(process.hProcess);
    return (int)result;
}
