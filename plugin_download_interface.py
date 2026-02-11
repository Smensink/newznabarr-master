from abc import ABC, abstractmethod

class PluginDownloadBase(ABC):

    @abstractmethod
    def getprefix(self):
        """The prefix for the the downloader supports"""
        pass

    @abstractmethod
    def download(self, url, title, download_dir, cat, progress_callback=None):
        """The download function"""
        pass
