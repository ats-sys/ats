import sys
import io


class StreamingOutputRedirector:
    """Custom output redirector for streaming out console logs"""
    def __init__(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.output = io.StringIO()

    def write(self, message):
        self.output.write(message)
        self.stdout.write(message)

    def flush(self):
        self.output.flush()
        self.stdout.flush()

    def get_output(self):
        # return self.output.getvalue().replace('\n', '<br>\n')
        return self.output.getvalue()