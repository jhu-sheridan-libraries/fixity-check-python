#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import filecmp
import os
import subprocess
import sys

"""
Author: Tim DiLauro <timmo@jhu.edu>
Dependencies:
- fixi ruby gem by Chris Wilper (https://github.com/cwilper/fixi)
"""

FIXI_CMD = '/usr/local/bin/fixi'
DEFAULT_MAIL_TO = ''
DEFAULT_MAILER = 'mailx'
DEFAULT_SUBJECT = 'Fixity Checking Results for:'
# Always send email or only send on error(s):
ALWAYS_SEND = True


def main():
    parser = argparse.ArgumentParser()
    # fixity checker options
    parser.add_argument('-c', '--fixi', dest='cmd_path', default=FIXI_CMD, help='path to fixi executable')
    parser.add_argument('--alg', dest='alg', default=None, help='hash algorithm for check (fails if algorithm not initialized')
    parser.add_argument('--details', dest='details', default=False, action='store_true', help='include details from fixity checking')
    parser.add_argument('--new', '--add_new', dest='add_new', default=False, action='store_true', help='send email even if no errors')

    # mail-related options
    parser.add_argument('-a', '--always_send', default=False, action='store_true', help='send email even if no errors')
    parser.add_argument('--mailer', dest='mailer', default=DEFAULT_MAILER, help='mailer command')
    parser.add_argument('-s', '--subject', dest='base_subject', default=DEFAULT_SUBJECT, help='mail subject prefix')
    parser.add_argument('--to',  '--mail-to',  dest='mail_to',  default=DEFAULT_MAIL_TO,
                        help='comma-separated email recipient list')
    parser.add_argument('--cc',  '--mail-cc',  dest='mail_cc',  default='', help='comma-separated email cc list')
    parser.add_argument('--bcc', '--mail-bcc', dest='mail_bcc', default='', help='comma-separated email bcc list')

    parser.add_argument('path', nargs='+', help='file/directory paths to check...')
    args = parser.parse_args()

    # fix/find the mailer path, if possible
    mailer_path = which(args.mailer)

    # todo: verify that fixi executable is where it's supposed to be... (die, if not)
    fixi_path = which(args.cmd_path)
    if fixi_path is None:
        warn("An executable fixity checker was not found at '%s'" % fixi_path)
        exit(1)

    recipients = args.mail_to

    if args.details:
        see_details = ' (see details below)'
    else:
        see_details = ''

    # if fixi algorithm not set or is 'all', then check using all algorithms
    if args.alg is None or args.alg == 'all':
        fixi_alg = []
    elif args.alg == 'none' or args.alg == 'shallow':
        fixi_alg = ['--shallow']
    else:
        fixi_alg = ['-l', args.alg]

    # filePath = os.path.abspath(argv[1])
    for filePath in args.path:

        mail_subject = args.base_subject + ' ' + filePath

        errors = False
        warnings = False
        msg_body = '  ' + filePath

        fixi_cmd_args = [fixi_path, 'check', '-a', '-v'] + fixi_alg + [filePath]
        p = subprocess.Popen(fixi_cmd_args, stdout=subprocess.PIPE)
        out = p.communicate()[0]
        p.stdout.close()
        if p.returncode > 0:
            warn("Error checking fixity on for '%s'; rc=%d\n%s" % (filePath, p.returncode, out))
            exit(p.returncode)

        output = out.splitlines()
        # print output

        changes = dict()
        changes['adds'] = [l for l in output if l.startswith('A ')]
        changes['mods'] = [l for l in output if l.startswith('M ')]
        changes['dels'] = [l for l in output if l.startswith('D ')]

        if len(changes['dels']) > 0:
            errors = True
            msg_body += '\n  %d file(s) reported deleted%s. ' % (
                        len(changes['dels']), see_details)

        if len(changes['mods']) > 0:
            errors = True
            msg_body += '\n  %d file(s) reported modified%s. ' % (
                        len(changes['mods']), see_details)

        if len(changes['adds']) > 0:
            warnings = True
            msg_body += '\n  %d file(s) reported added%s. ' % (
                        len(changes['adds']), see_details)

        if errors:
            msg_body = 'Errors detected during fixity checking of...\n' + msg_body
            subject = '[ERROR] ' + mail_subject
        elif warnings:
            msg_body = 'Warnings detected during fixity checking of...\n' + msg_body
            subject = '[WARNING] ' + mail_subject
        else:
            msg_body = 'No problems detected during fixity checking of...\n' + msg_body
            subject = '[INFO] ' + mail_subject

        msg_body += '\n\n Cmd: %s' % (fixi_cmd_args)

        if args.details:
            if len(changes['dels']) > 0:
                msg_body += '\n\nFiles reported as deleted (%d):' % len(changes['dels'])
                for change in changes['dels']:
                    msg_body += '\n  %s' % change.split(' ', 1)[1]

            if len(changes['mods']) > 0:
                msg_body += '\n\nFiles reported as modified (%d):' % len(changes['mods'])
                for change in changes['mods']:
                    msg_body += '\n  %s' % change.split(' ', 1)[1]

            if len(changes['adds']) > 0:
                msg_body += '\n\nFiles reported as added (%d):' % len(changes['adds'])
                for change in changes['adds']:
                    msg_body += '\n  %s' % change.split(' ', 1)[1]

        if errors or warnings:
            msg_body += '\n\n For more information, run:\n  %s check -a %s' % (fixi_path, filePath)

        if args.add_new and len(changes['adds']) > 0:
            msg_body += '\n\nAutomatically adding new files (%d) to fixity database:' % len(changes['adds'])
            for change in changes['adds']:
                added_path = change.split(' ', 1)[1]
                msg_body += '\n  Adding %s' % change.split(' ', 1)[1]

                fixi_cmd_args = [fixi_path, 'add'] + [added_path]
                p = subprocess.Popen(fixi_cmd_args, stdout=subprocess.PIPE)
                out = p.communicate()[0]
                p.stdout.close()
                if p.returncode > 0:
                    warn("Error checking fixity on for '%s'; rc=%d\n%s" % (filePath, p.returncode, out))
                    exit(p.returncode)
            msg_body += '\nCompleted additions to fixity database.\n'


        print(msg_body)

        if ALWAYS_SEND or errors or warnings:
            # send the message
            # todo: replace this using smtplib
            p = subprocess.Popen((mailer_path, '-s', subject, '-c', args.mail_cc, '-b', args.mail_bcc, recipients),
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.stdin.write(msg_body)
            mail_out, mail_err = p.communicate()

            if p.returncode > 0:
                warn("Error sending mail for path '%s'; rc=%d\n%s\n%s" % (filePath, p.returncode, mail_out, mail_err))
                exit(p.returncode)

        print('\n *processing completed*')


def which(program):
    import os

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def warn(*args, **kwargs):
    """ Emit a warning in the style of Python 3.x print() function
    :param args: objects to print
    :param prefix: text to prepend to output, default is 'WARNING: '
    :param kwargs:
    :return: None
    """
    default_prefix = 'WARNING: '
    prefix = kwargs.pop('prefix', default_prefix)
    print(prefix, *args, file=sys.stderr, **kwargs)
    return


if __name__ == '__main__':
    main()
