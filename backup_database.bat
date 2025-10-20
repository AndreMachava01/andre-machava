@echo off
echo Executando backup do banco de dados...
cd /d "%~dp0"
python manage.py backup_db
echo Backup concluído!
pause
