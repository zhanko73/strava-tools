
import click_shell
import click

# Override ClickShell to add a on_finish operation
class ClickShell(click_shell.core.ClickShell):
    def __init__(self, ctx=None, hist_file=None, on_finish=None, *args, **kwargs):
        super(ClickShell, self).__init__(ctx, hist_file, *args, **kwargs)
        self.on_finish = on_finish

    def postloop(self):
        super(ClickShell, self).postloop()
        if self.on_finish:
            self.on_finish(self.ctx)

class Shell(click_shell.core.Shell):
     def __init__(self, prompt=None, intro=None, hist_file=None, on_finish=None, **attrs):
        attrs['invoke_without_command'] = True
        super(Shell, self).__init__(**attrs)

        # Make our shell
        self.shell = ClickShell(hist_file=hist_file, on_finish=on_finish)
        self.shell.prompt = prompt
        self.shell.intro = intro

# override decorators
def shell(name=None, **attrs):
    attrs.setdefault('cls', Shell)
    return click.command(name, **attrs)