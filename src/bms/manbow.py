from __future__ import annotations
import sys
import logging
import json
from collections import namedtuple
from dataclasses import dataclass
from typing import ClassVar
from pathlib import Path
import os
import requests
from bs4 import BeautifulSoup, Tag
import re

import gdown
from gdown.parse_url import is_google_drive_url
from gdown import FileURLRetrievalError, DownloadError
import patoolib
from patoolib.util import PatoolError


logger = logging.getLogger(__name__) # to-do: where to place this line of code?

@dataclass
class Track:
    event: str
    num: str
    artists: str
    team: str
    title: str
    size: str
    addr: Tag



@dataclass
class Task:
    event: str
    save_to: Path
    start: str = '1'
    end: str = '999'
    SITE: ClassVar[str] = "https://manbow.nothing.sh/event/event.cgi?action=URLList"


    @classmethod
    def from_sysargv(cls, argv: list) -> Task:
        _, event, save_to, *start_and_end = argv
        return cls(
            event, 
            Path(save_to), 
            *start_and_end,
        )


    def run(self):
        html = self._fetch_html()
        layout = self._inspect(html)
        tracks = self._get_track_data(html, layout)

        
        failed = []
        for track in tracks:
            track_dir = self._mkdir(track)
            urls = self._get_urls(track)
            if self._track_has_multiple_urls(urls):
                self._log_multiple_urls(track.num)

            for link_num, url in enumerate(urls, start=1):
                self._print_horizontal_line()
                self._print_now_processing(track.num, link_num) 

                download = self._dispatch(url)
                res = download(url, track_dir)
                if res is None: 
                    failed.append({
                        'track_dir': str(track_dir),
                        'url': url,
                        'direct_url': None,
                    })
                    self._log_unsupported_link(
                        track.num, 
                        link_num, 
                        url,
                    )
                    continue
                elif isinstance(res, Exception):
                    failed.append({
                        'track_dir': str(track_dir),
                        'url': url,
                        'direct_url': None,
                    })
                    self._log_error(
                        res, 
                        track.num, 
                        link_num, 
                        url,
                    )
                    continue  

                extr_res = self._extract(res)
                if extr_res is None:
                    self._log_not_an_archive(
                        track.num, 
                        link_num, 
                        url,
                    )
                if isinstance(extr_res, Exception):
                    self._log_error(
                        extr_res, 
                        track.num, 
                        link_num, 
                        url,
                    )
                    continue

        self._export_json(failed)


    def _fetch_html(self) -> BeautifulSoup:
        params = {
            'event':self.event, 
            'start':self.start, 
            'end':self.end,
        }
        html = requests.get(self.SITE, params=params).content.decode('Shift_JIS')
        return BeautifulSoup(html, 'html5lib')
    

    def _inspect(self, html: BeautifulSoup) -> str:
        """
        The manbow website has two differrent layouts, and this method is used to tell which one the event page belongs to.
        """
        headers = [th.text for th in html.thead.find_all('th')]
        match headers:
            case [
                'No', 
                'Name', 
                'Team', 
                'Title', 
                'Size', 
                'Addr',
            ]:
                return "has_team" 
                # has the "team" column.
            case [
                'No', 
                'Name', 
                'Title', 
                'Size', 
                'Addr',
            ]:
                return "doesn\'t_have_team"
                # doesn't have the "team" column.
            case _:
                raise Exception(f'Match-case failed. headers: {headers}.')


    def _get_track_data(self, html: BeautifulSoup, layout: str) -> list[Track]:
        tracks = []
        rows = [tr.find_all('td') for tr in html.tbody.find_all('tr')]
        for row in rows:
            match layout, row:
                case "has_team", [num, artists, team, title, size, addr]:
                    tracks.append(
                        Track(
                            self.event,
                            num.text,
                            artists.text,
                            team.text,
                            title.text,
                            size.text,
                            addr,
                        ) 
                    ) 
                case "doesn\'t_have_team", [num, artists, title, size, addr]:
                    tracks.append(
                        Track(
                            self.event,
                            num.text,
                            artists.text,
                            None,
                            title.text,
                            size.text,
                            addr,
                        ) 
                    ) 
                case _:
                    raise Exception(f'Match-case failed. layout: {layout}, row_data: {row_data}.')
        return tracks


    def _mkdir(self, track) -> Path:
        name = self._validate(
            f'{track.num:0>3}. {track.title} (by {track.artists})'
        )
        track_dir = self.save_to / name 
        track_dir.mkdir(parents=True, exist_ok=True)
        return track_dir


    def _get_urls(self, track: Track) -> list[str]:
        return [ a['href'] for a in track.addr.find_all('a')]


    def _track_has_multiple_urls(self, urls) -> bool:
        return len(urls) != 1


    def _validate(self, data: str) -> str: 
        if len(data) > 255:
            data = data[:255]
        return re.sub(r'[*"/\<>:|?]', '_', data)


    def _print_now_processing(self, track_num: str, link_num: int) -> None: 
        print(
            f'Processing track {track_num}, link {link_num}...'
        )

    
    def _print_horizontal_line(self) -> None:
        term_width = os.get_terminal_size()
        print(
            '-' * term_width.columns
        )


    def _log_multiple_urls(self, track_num: str) -> None:
        term_width = os.get_terminal_size()
        horizontal_line = '-' * term_width.columns
        logger.info(
            f'\n'
            f'track {track_num}\n'
            f'There\'s multiple downloadable links in this track.\n'
            f'{horizontal_line}'
        )


    def _log_unsupported_link(self, 
        track_num: str, 
        link_num: int, 
        url: str,
    ) -> None:
        term_width = os.get_terminal_size()
        horizontal_line = '-' * term_width.columns
        logger.info(
            f'\n'
            f'track {track_num}, link {link_num}\n'
            f'Can not find a proper way to download this file.\n'
            f'{horizontal_line}'
        )


    def _log_error(
        self, 
        error: FileURLRetrievalError | DownloadError | PatoolError, 
        track_num: str, 
        link_num: int, 
        url: str,
    ) -> None: 
        term_width = os.get_terminal_size()
        horizontal_line = '-' * term_width.columns
        logger.info(
            f'\n'
            f'Track {track_num}, link {link_num}\n'
            f'{type(error).__name__}\n'
            f'{error}\n'
            f'{horizontal_line}'
        )


    def _log_not_an_archive(
        self, 
        track_num: str, 
        link_num: int, 
        url: str,
    ) -> None: 
        term_width = os.get_terminal_size()
        horizontal_line = '-' * term_width.columns
        logger.info(
            f'\n'
            f"track {track_num}, link {link_num}\n"
            f'There\' probably an attachment in this directory.\n'
            f'{horizontal_line}'
        )


    def _dispatch(self, url: str) -> self._dl_google_folder | self._dl_google_file | self._dl_dropbox:
        dispatch_table = { 
            self._is_google_folder: self._dl_google_folder,
            self._is_google_file: self._dl_google_file, 
            self._is_dropbox: self._dl_dropbox,
        }
        for matches, do in dispatch_table.items():
            if matches(url):
                return do
        return self._handle_unmatched_link


    def _is_google_file(self, url: str) -> bool:
        return is_google_drive_url(url) and not self._is_google_folder(url)


    def _is_google_folder(self, url: str) -> bool: # to-do: move this method to another module.
        return re.search(r'/drive/folders', url)


    def _is_dropbox(self, url: str) -> bool: # to-do: move this method to another module.
        return re.search(r'dropbox\.com', url)


    def _dl_google_file(self, url: str, track_dir: Path) -> Path | FileURLRetrievalError | DownloadError: 
        output = str(track_dir) + os.path.sep  
        try:
            saved = gdown.download(
                url=url, 
                output=output,
            )
            # gdown.download: output expects str. If it ends with a path sep, the basename will be appended automatically.
        except (
            FileURLRetrievalError,
            DownloadError,
        ) as error:
            print('Skip. (a gdown error has occurred)')
            return error

        else:
            return Path(saved)

        
    def _dl_google_folder(self, url: str, track_dir: Path) -> Path | DownloadError: # to-do: fix the error
        output = str(track_dir) + os.path.sep  
        try:
            saved = gdown.download_folder(
                url=url, 
                output=output,
            ) 
            # gdown.download_folder: output expects str. If it ends with a path sep, the basename will be appended automatically.
        except DownloadError as error:
            print('Skip. (A gdown error has occurred)')
            return error

        else:
            return Path(saved)


    def _dl_dropbox(self, url: str, track_dir: Path) -> Path | DownloadError: # to-do: check if the file downloaded is a html or not. 
        url = re.sub('dl=0', 'dl=1', url)
        output = str(track_dir) + os.path.sep  
        try:
            saved = gdown.download(
                url=url, 
                output=output,
            )
            # gdown.download: output expects str. If it ends with a path sep, the basename will be appended automatically.
        except DownloadError as error:
            print('Skip. (A gdown error has occurred)')
            return error

        else:
            return Path(saved)


    def _handle_unmatched_link(self, andchor: Tag, track_dir: Path) -> None: # to-do: handle unmatched track properly.
        print('Skip. (unsupported URL host)')
        return None


    def _extract(self, saved: Path) -> str | None | PatoolError: 
        if not patoolib.is_archive(saved): 
            return None 
        try:
            patoolib.extract_archive(
                str(saved), 
                outdir=str(saved.parent), 
                interactive=False, 
                verbosity=-1
            )
        except PatoolError as error:
            return error

        saved.unlink() 
        return 'successful'


    def _handle_filedepth(self, track_dir: Path):
        pass


    def _export_json(self, failed: list[dict]) -> None:
        with open('failed.json', mode='w', encoding='utf-8') as file:
            json.dump(failed, file, indent=4)




def main():
    logging.basicConfig( # to-do: refactor logging features.
        filename='log.txt', 
        filemode='w', 
        encoding='utf-8', 
        level=logging.INFO,
    ) 

    if len(sys.argv) >= 3:
        task = Task.from_sysargv(sys.argv)
        task.run()
    else: 
        print('Requires at least 2 arguments: the event number and the output filepath')  


if __name__ == '__main__':  
    main()




# to-do: move the logging functions to a separate script.
# to-do: log the file path after gdown.download finished if the file is broken.
# patool: different MIME types detected
# inspect gdown.download parameter. Find a way (if there is one) to show only the download progress bar on terminal.
# gdown.download: The speed, callback, and log_message parameters.

# The ability to recognize and integrate different file catogories of a same song (.wav, .ogg, additional BGA file).
# Google folders
