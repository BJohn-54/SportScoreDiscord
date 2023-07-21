import datetime
import os
import traceback

def log_exception_traceback(e):
    print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
    if not os.path.exists('logs.txt'):
        with open('logs.txt', 'w', encoding='utf-8'):
            pass

    with open('logs.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open('logs.txt', 'w', encoding='utf-8') as f:
        new_log_entry = '\n' + str(datetime.datetime.now()) + '\n'
        new_log_entry += ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        lines = [new_log_entry] + lines
        lines = lines[:20000]

        f.writelines(lines)
    
def log_last_traceback(exc_type, exc_value, exc_traceback):
    print(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    if not os.path.exists('logs.txt'):
        with open('logs.txt', 'w', encoding='utf-8'):
            pass

    with open('logs.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    with open('logs.txt', 'w', encoding='utf-8') as f:
        new_log_entry = '\n' + str(datetime.datetime.now()) + '\n'
        new_log_entry += ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        lines = [new_log_entry] + lines
        lines = lines[:20000]

        f.seek(0)
        f.writelines(lines)