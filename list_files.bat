@echo off
setlocal enabledelayedexpansion

REM Output file name
set "output_file=file_list.txt"

REM Function to print directory tree and files with dynamic headers
:print_directory_tree
(
  echo Date and Time: %date% %time:~0,8%
  echo Directory Structure and Files in .\app:
  tree /F .\app
  echo.
  echo Details of Files:
  
  for /r .\app %%f in (*) do (
    set "file=%%f"
    for %%b in ("!file!") do (
      set "ext=%%~xb"
      if /I not "!ext!"==".exe" (
        if /I not "!ext!"==".dll" (
          echo ___________
          echo Start of file: !file!
          type "!file!"
          echo End of file: !file!
          echo ___________
        ) else (
          echo Binary File: !file!
        )
      ) else (
        echo Binary File: !file!
      )
    )
  )
) > "%output_file%"

echo Script finished. Output saved to %output_file%
exit /b
