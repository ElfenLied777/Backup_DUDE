#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-
import os
import pexpect
import csv
import re
import subprocess
from datetime import date
from time import sleep
import smtplib
from email.mime.multipart import MIMEMultipart      # Многокомпонентный объект
from email.mime.text import MIMEText                # Текст/HTML
from email.header import Header
import sys

USERNAME = os.environ.get('TELNET_USER')
USERNAME1 = 'rsvo_robot'
PASSWORD = os.environ.get('TELNET_PASSWORD')
ip_dude1 = '172.31.1.38'
ip_dude2 = '172.31.1.39'
regex_files = re.compile(r'(?P<number>\d+)\s+(?P<name>backup_\d{2}_\d{2}_\d{4}).*') #регулярное выражение для поиска всех старых файлов backup в файловой системе для дальнейшего их удаления
backup_file_name = 'backup_{}'.format(date.today().strftime('%d_%m_%Y')) # название файла backup

def mail(result):
    msg = MIMEMultipart()                               # Создаем сообщение
    msg['From']    = "admin@spb.rsvo.ru"
    msg['To']      = "admin@spb.rsvo.ru"
    msg['Subject'] = Header('THE DUDE backup', 'utf-8')
    msg.attach(MIMEText(result, 'plain','utf-8'))
    server = smtplib.SMTP('192.168.21.209')           # Создаем объект SMTP
    server.send_message(msg)                            # Отправляем сообщение
    server.quit()

def dude_backup(dude,ip,backup_file_name):
    try:
        with pexpect.spawn('telnet {}'.format(ip),encoding='utf-8') as telnet:
            telnet.expect('[Ll]ogin:')
            telnet.sendline(USERNAME1)
            telnet.expect('[Pp]assword:')
            telnet.sendline(PASSWORD)
            telnet.expect('>')
            telnet.expect('>')

            telnet.sendline('file print without-paging\r') # вывести все файлы, хранящиеся на сервере
            telnet.expect('>')
            telnet.expect('>')
            show_output = telnet.before
            for line in show_output.split('\n'):
                match = re.search(regex_files, line) # поиск файлов backup
                if match:
                    if match.group('name') == backup_file_name: # если имя файла backup совпадает с файлом сегодняшего дня, то оставить его на сервере, остальные старые файлы backup удалить
                        continue
                    else:
                        telnet.sendline('file remove numbers={}\r'.format(match.group('number')))
                        telnet.expect('>')
                        telnet.expect('>')

            if dude == 1: # работы на сервере DUDE#1
                telnet.sendline('dude export-db backup-file={}\r'.format(backup_file_name)) # создание файла backup - появляется в файловой системе DUDE
            elif dude == 2: # работы на сервере DUDE#2
                telnet.sendline('dude import-db backup-file={}\r'.format(backup_file_name)) # обновление конфигурации на резервном сервере DUDE#2
            sleep(600)
            telnet.expect('>')
            telnet.expect('>')
            telnet.sendline('quit')

    except pexpect.TIMEOUT:
        with open('dude_backup_log/log.txt','a') as f:
            f.write('{} - dude#{} has not been backuped for TIMEOUT'.format(backup_file_name,dude))
        mail('{} - dude#{} has not been backuped for TIMEOUT'.format(backup_file_name,dude))# отправка по почте письма с информированием об исключении
    except pexpect.EOF:
        with open('dude_backup_log/log.txt','a') as f:
            f.write('{} - dude#{} has not been backuped for EOF'.format(backup_file_name,dude))
        mail('{} - dude#{} has not been backuped for EOF'.format(backup_file_name,dude)) # отправка по почте письма с информированием об исключении


if __name__ == '__main__':
    print(USERNAME)
    print(PASSWORD)
    dude_backup(1,ip_dude1,backup_file_name) # функция по созданию backup на сервере DUDE#1
    result_download_from_dude1 = subprocess.call(['wget','--user={}'.format(USERNAME),'--password={}'.format(PASSWORD), '--output-document=dude_backup_file/{}'.format(backup_file_name),'ftp://172.31.1.38/{}'.format(backup_file_name)]) # скачать файл backup на nas в директорию dude_backup_file
    if result_download_from_dude1 != 0:
        mail('dude_backup_file {} НЕ скачался на сервер nas с DUDE#1'.format(backup_file_name))
    else:
        result_upload_to_dude2 = subprocess.call(['curl', '-T', 'dude_backup_file/{}'.format(backup_file_name), '-u',' {}:{}'.format(USERNAME,PASSWORD), 'ftp://172.31.1.39']) #загрузить файл backup с nas на DUDE#2
        if result_upload_to_dude2 != 0:
            mail('dude_backup_file {} НЕ загрузился с nas на DUDE#2'.format(backup_file_name))
        else:
            dude_backup(2,ip_dude2,backup_file_name) # функция по созданию backup на сервере DUDE#2
