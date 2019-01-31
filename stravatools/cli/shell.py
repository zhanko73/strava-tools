
import click, os
from click_shell import shell
from stravatools import __version__
from stravatools.client import Client
from stravatools.cli import commands
from stravatools.cli.commands import *

histfile = os.path.join(os.path.expanduser("~"), ".strava_history")

@shell(prompt='strava >> ', intro='Strava Shell %s' % __version__, hist_file=histfile)
@click.option('--cert', help='Path SSL certificat Root CA')
@click.option('-v', '--verbose', count=True)
@click.pass_context
def cli_shell(ctx, cert, verbose):
    client = ctx.obj['client']
    greeting(client)

for command in commands.__dict__.values():
    if isinstance(command, click.core.Command):
        cli_shell.add_command(command)

@click.command()
@click.option('--cert', help='Path SSL certificat Root CA')
@click.option('-v', '--verbose', count=True)
def main(cert, verbose):
    cli_shell(obj = {'client': Client(cert=cert, debug=verbose)})

if __name__ == '__main__':
    main()