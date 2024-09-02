import logging
import requests
import os
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install
from rich.table import Table
import pandas as pd

class CustomLogger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CustomLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_file_path="logs/automation.log", debug_mode=False, error_webhook_url=None):
        if self._initialized:
            return
        self.console = Console()
        self.debug_mode = debug_mode
        self.error_webhook_url = error_webhook_url

        # Ensure the log directory exists
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Setup rich for pretty tracebacks
        install(show_locals=True, suppress=[logging])

        # Configure logging
        self.logger = logging.getLogger("custom_logger")
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

        # Add RichHandler for console output
        rich_handler = RichHandler(console=self.console, markup=True, rich_tracebacks=True)
        self.logger.addHandler(rich_handler)

        # Add file handler
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)

        self._initialized = True

    def log(self, level, message):
        if level == "debug" and not self.debug_mode:
            return
        if level == "debug":
            self.logger.debug(message)
        elif level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
            self._send_error_notification(message)
        elif level == "critical":
            self.logger.critical(message)
            self._send_error_notification(message)

    def log_exception(self, ex):
        self.logger.exception(f"Exception occurred: {str(ex)}")
        self._send_error_notification(str(ex))

    def log_table(self, headers, rows):
        table = Table(show_header=True, header_style="bold magenta")
        for header in headers:
            table.add_column(header)

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    def log_dataframe(self, df: pd.DataFrame):
        """
        Logs the content of a DataFrame as a table in the console.

        :param df: The DataFrame to log.
        """
        if df.empty:
            self.logger.info("DataFrame is empty.")
            return

        headers = df.columns.tolist()
        rows = df.astype(str).values.tolist()
        self.log_table(headers, rows)

    def _send_error_notification(self, message):
        if self.error_webhook_url:
            try:
                response = requests.post(self.error_webhook_url, json={"error": message})
                if response.status_code != 200:
                    self.logger.warning(f"Failed to send error notification: {response.status_code}")
            except Exception as e:
                self.logger.warning(f"Exception during error notification: {str(e)}")

    @staticmethod
    def get_instance():
        if CustomLogger._instance is None:
            raise Exception("CustomLogger not initialized. Call CustomLogger() first.")
        return CustomLogger._instance

    @staticmethod
    def initialize_from_env():
        debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        error_webhook_url = os.getenv("ERROR_WEBHOOK_URL")
        return CustomLogger(debug_mode=debug_mode, error_webhook_url=error_webhook_url)


# # Example usage in other classes/modules
# class ExampleClass:
#     def __init__(self):
#         self.logger = CustomLogger.get_instance()

#     def run(self):
#         try:
#             # Your code logic here
#             self.logger.log("info", "Running ExampleClass logic.")
#             df = pd.DataFrame({
#                 'Name': ['Alice', 'Bob', 'Charlie'],
#                 'Age': [24, 30, 22],
#                 'City': ['New York', 'Los Angeles', 'Chicago']
#             })
#             self.logger.log_dataframe(df)
#             raise ValueError("An example error.")
#         except Exception as e:
#             self.logger.log_exception(e)


# if __name__ == "__main__":
#     # Initialize the logger from environment variables
#     logger = CustomLogger.initialize_from_env()

#     # Use the logger in a different class/module
#     example = ExampleClass()
#     example.run()