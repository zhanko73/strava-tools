
import click, os
from click_shell import shell
from stravatools import __version__
from stravatools.client import Client
from stravatools.cli import commands
from stravatools.cli.commands import *

histfile = os.path.join(os.path.expanduser("~"), ".strava_history")

@shell(prompt='strava >> ', intro='Strava Shell %s' % __version__, hist_file=histfile)
@click.pass_context
def cli_shell(ctx):
    client = ctx.obj['client']
    greeting(client)

@click.command()
@click.option('--cert', help='Path SSL certificat Root CA')
@click.option('-v', '--verbose', count=True)
def main(cert, verbose):
    """Simple program that greets NAME for a total of COUNT times."""
    
    cli_shell(obj = {'client': Client(cert=cert, debug=verbose)})

for command in commands.__dict__.values():
    if isinstance(command, click.core.Command):
        cli_shell.add_command(command)

if __name__ == '__main__':
    main()