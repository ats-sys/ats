from threading import Thread
from deepdiff import DeepDiff
from typing import Literal
from ats.trading_job.trading_job import TradingJob
from ats.exchanges.plot_data import PlotData
from ats.exceptions import trading_job_exceptions
from ats.utils.logging.logger import logger


class TradingJobManager:
    """
    Trading job manager creates and manages TradingJob objects
    Each TradingJob is run in a separate thread within this class
    """
    def __init__(self):
        self._trading_jobs = {}

    def create_job(self, config: dict) -> str:
        """
        Create a trading job, give a config.
        Created trading jobs must be triggered for running seperately
        Args:
            config:

        Returns:
            Trading job id
        """
        trading_job = TradingJob()
        self._trading_jobs[trading_job.id] = {
            'trading_job': trading_job,
            'processing_thread': None
        }

        trading_job.set_config(config)
        logger.info(f"New trading job created. Id: {trading_job.id}")
        return trading_job.id

    def run_job(self, job_id: str) -> None:
        """
        Runs a trading job given job id
        Args:
            job_id: Trading job id

        Returns:
            None
        """
        if job_id not in self._trading_jobs:
            raise trading_job_exceptions.TradingJobNotFoundException(f"Couldn't run because no job found for id: {job_id} ")

        trading_job: TradingJob = self._trading_jobs[job_id]['trading_job']

        if trading_job.is_running:
            raise trading_job_exceptions.TradingJobAlreadyRunningException(f'Trading job {job_id} cannot be run because'
                                                                           f' it is already running.')
        trading_job.load_exchange()
        trading_job.load_strategy()

        self._trading_jobs[job_id]['processing_thread'] = Thread(target=trading_job.run)
        # self._trading_jobs[job_id]['processing_thread'].daemon = True
        self._trading_jobs[job_id]['processing_thread'].start()
        logger.info(f"Trading job is running. id: {job_id}")

    def stop_job(self, job_id: str) -> None:
        """
        Stops a trading job given job id
        Args:
            job_id: Trading job id

        Returns:
            None
        """
        if job_id not in self._trading_jobs:
            raise trading_job_exceptions.TradingJobNotFoundException(f"Couldn't stop because no job found for id: {job_id} ")

        trading_job: TradingJob = self._trading_jobs[job_id]['trading_job']
        processing_thread = self._trading_jobs[job_id]['processing_thread']

        if processing_thread is None:
            raise trading_job_exceptions.TradingJobNotRunningException(
                f"Cannot stop trading job. Job not running for id: {job_id}")

        # processing_thread is not None and not processing_thread.is_alive()

        trading_job.stop()
        processing_thread.join()
        self._trading_jobs[job_id]['processing_thread'] = None
        logger.info(f"Trading job is stopped. id: {job_id}")

    def get_job_status(self, job_id: str) -> dict:
        """
        Get the trading job status given the id
        Args:
            job_id: Job id
        Returns:
            Trading job status
        """
        if job_id not in self._trading_jobs:
            raise trading_job_exceptions.TradingJobNotFoundException(f"Couldn't get job status because no job found for id: {job_id}")
        return self._trading_jobs[job_id]['trading_job'].get_status()

    def get_all_jobs(self) -> list:
        """
        Get the job ids of all jobs
        Returns:
            Returns the list of job ids with basic status details
        """
        result = []

        for job_id, job in self._trading_jobs.items():
            job_status = job['trading_job'].get_status()
            result.append(job_status)

        return result

    def reload_job(self, config: dict, job_id: str):
        """
        Reloads a trading job by looking at the differences in the config.
        Args:
            config: Trading job configuration
            job_id: Job id
        Returns:
            None
        """

        # IMPORTANT: It is not possible to reload the exchange. Exchanges probably use websocket streams for syncing events.

        if job_id not in self._trading_jobs:
            raise trading_job_exceptions.TradingJobNotFoundException(f"Couldn't reload because no job found for id: {job_id} ")

        trading_job: TradingJob = self._trading_jobs[job_id]['trading_job']

        trading_job.set_config(config)

        trading_job.load_strategy()

    def get_job_plot_data(self, job_id: str) -> PlotData:
        """
        Get the trading job plot data given the id
        Args:
            job_id: Job id
        Returns:
            Trading job status
        """
        if job_id not in self._trading_jobs:
            raise trading_job_exceptions.TradingJobNotFoundException(f"Couldn't get job status because no job found for id: {job_id}")
        return self._trading_jobs[job_id]['trading_job'].get_plot_data()



