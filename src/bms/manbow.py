from __future__ import annotations
import sys
import logging
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
import os
import requests
from bs4 import BeautifulSoup, Tag
import re

import gdown
from gdown.parse_url import is_google_drive_url
from gdown import FileURLRetrievalError, DownloadError
import patoolib


logger = logging.getLogger(__name__) # to-do: where to place this line of code?

Track = namedtuple('Track', [
    'event', 
    'num', 
    'artists', 
    'team', 
    'title', 
    'size', 
    'addr',
])

Error = namedtuple('Error', [
    'type',
    'msg',
])




@dataclass
class Task:
    event: int 
    save_to: Path
    start: int = 1
    end: int = 999
    SITE = "https://manbow.nothing.sh/event/event.cgi?action=URLList" # to-do: implement it as a class constant.


    @classmethod
    def from_sysargv(cls, argv: list) -> Task:
        _, event, save_to, start, end = argv
        return cls(
            event, 
            Path(save_to), 
            start, 
            end,
        )


    def run(self):
        soup = self._fetch_html()
        has_team = self._inspect_headers(soup)
        tracks = self._get_tracks(soup, has_team)

        li = [] # to-do: rename the variable.
        for track in tracks:    # to-do: show the track number clearly before self._download()
            track_dir = self._mkdir(track)
            anchors = track.addr.find_all('a')
            if len(anchors) != 1:
                li.append(track)

            for index, anchor in enumerate(anchors, start=1):
                self._print_horizontal_line()
                self._print_msg(track.num, index)

                result = self._download(anchor, to=track_dir)
                if isinstance(result, Error):
                    self._log_error(result, track.num, index, anchor)
                    continue  
                if result is None: # to-do: record the track number.
                    continue

                result = self._extract(result)
                if isinstance(result, Error):
                    self._log_error(result, track.num, index, anchor)



    def _fetch_html(self) -> BeautifulSoup:
        params = {
            'event':self.event, 
            'start':self.start, 
            'end':self.end,
        }
        html = requests.get(self.SITE, params=params).content.decode('Shift_JIS')
        return BeautifulSoup(html, 'html5lib')
    

    def _inspect_headers(self, soup) -> bool:
        headers = [th.text for th in soup.thead.find_all('th')]
        match headers:
            case [
                'No', 
                'Name', 
                'Team', 
                'Title', 
                'Size', 
                'Addr',
            ]:
                return True 
                # has the "team" column.
            case [
                'No', 
                'Name', 
                'Title', 
                'Size', 
                'Addr',
            ]:
                return False 
                # doesn't have the "team" column. 
            case _:
                raise Exception(f'Match-case failed. headers: {headers}.')


    def _get_tracks(self, soup, has_team: bool) -> list[Track]:
        tracks = []
        rows = [tr.find_all('td') for tr in soup.tbody.find_all('tr')]
        for row in rows:
            match has_team, row:
                case True, [num, artists, team, title, size, addr]:
                    tracks.append(
                        Track(
                            self.event,
                            int(num.text),
                            artists.text,
                            team.text,
                            title.text,
                            size.text,
                            addr,
                        ) 
                    ) 
                case False, [num, artists, title, size, addr]:
                    tracks.append(
                        Track(
                            self.event,
                            int(num.text),
                            artists.text,
                            None,
                            title.text,
                            size.text,
                            addr,
                        ) 
                    ) 
                case _:
                    raise Exception(f'Match-case failed. has_team: {has_team}, row_data: {row_data}.')
        return tracks


    def _mkdir(self, track) -> Path:
        name = self._validate(
            f'{track.num}. {track.title} (by {track.artists})'
        )
        track_dir = self.save_to / name 
        track_dir.mkdir(parents=True, exist_ok=True)
        return track_dir


    def _validate(self, data: str) -> str: 
        if len(data) > 255:
            data = data[:255]
        return re.sub(r'[*"/\<>:|?]', '_', data)


    def _print_msg(self, track_num: int, index: int) -> None: # to-do: rename the method.
        print(
            f'Processing track {track_num}, link {index}...'
        )

    
    def _print_horizontal_line(self) -> None:
        term_width = os.get_terminal_size()
        print(
            '-' * term_width.columns
        )


    def _log_error(
        self, 
        error: Error, 
        track_num: int, 
        index: int, 
        anchor: Tag,
    ) -> None: 
        term_width = os.get_terminal_size()
        horizontal_line = '-' * term_width.columns
        logger.info(
            f'\n'
            f'{error.type.__name__} in track {track_num}, link {index}\n'
            f'{error.msg}\n'
            f'{horizontal_line}'
        )


    def _download(self, anchor: Tag, to: Path) -> Path | None | Error: 
        match_host = { 
            is_google_drive_url: self._dl_google_file, 
            self._is_google_folder: self._dl_google_folder,
            self._is_dropbox: self._dl_dropbox,
            self._match_all: self._handle_unmatched_track,
        }
        for match, download in match_host.items(): # to-do: rename the variables.
            if match(anchor['href']):
                return download(anchor, to) 


    def _is_dropbox(self, url: str) -> bool: # to-do: move this method to another module.
        return re.search(r'dropbox\.com', url)


    def _is_google_folder(self, url: str) -> bool: # to-do: move this method to another module.
        return re.search(r'\drive\folders', url)


    def _match_all(self, url:str) -> bool: # to-do: move this method to another module.
        return True


    def _dl_google_file(self, anchor: Tag, track_dir: Path) -> Path | Error: 
        output = str(track_dir) + os.path.sep  
        try:
            saved = gdown.download(
                url=anchor['href'], 
                output=output,
            )
            # gdown.download: output expects str. If it ends with a path sep, the basename will be appended automatically.
        except FileURLRetrievalError as e:
            print('Skip. (a gdown error has occurred)')
            return Error(
                FileURLRetrievalError,
                e,
            )
        except DownloadError as e:
            print('Skip. (A gdown error has occurred)') # to-do: Can I combine these two excepts into one?
            return Error(
                DownloadError, 
                e,
            )
        else:
            return Path(saved)

        
    def _dl_google_folder(self, anchor: Tag, track_dir: Path) -> Path | Error: 
        output = str(track_dir) + os.path.sep  
        try:
            saved = gdown.download_folder(
                url=anchor['href'], 
                output=output,
            ) 
            # gdown.download_folder: output expects str. If it ends with a path sep, the basename will be appended automatically.
        except FileURLRetrievalError as e:
            print('Skip. (a gdown error has occurred)')
            return Error(
                FileURLRetrievalError,
                e,
            )
        except DownloadError as e:
            print('Skip. (A gdown error has occurred)') # to-do: Can I combine these two excepts into one?
            return Error(
                DownloadError, 
                e,
            )
        else:
            return Path(saved)


    def _dl_dropbox(self, anchor: Tag, track_dir: Path) -> Path | Error:
        url = re.sub('dl=0', 'dl=1', anchor['href'])
        output = str(track_dir) + os.path.sep  
        try:
            saved = gdown.download(
                url=url, 
                output=output,
            )
            # gdown.download: output expects str. If it ends with a path sep, the basename will be appended automatically.
        except FileURLRetrievalError as e:
            print('Skip. (a gdown error has occurred)')
            return Error(
                FileURLRetrievalError,
                e,
            )
        except DownloadError as e:
            print('Skip. (A gdown error has occurred)') # to-do: Can I combine these two excepts into one?
            return Error(
                DownloadError, 
                e,
            )
        else:
            return Path(saved)


    def _handle_unmatched_track(self, andchor: Tag, to: Path) -> None: # to-do: handle unmatched track properly.
        print('Skip. (unsupported URL host)')
        return None


    def _extract(self, saved: Path) -> None | Error: 
        if not patoolib.is_archive(saved): 
            return # to-do: log the file path.
        try:
            print('Extracting...')
            patoolib.extract_archive( # to-do: could not find an executable program to extract format rar; candidates are rar,unrar,7z,7zz,7zzs,unar
                str(saved), 
                outdir=str(saved.parent), 
                interactive=False, 
                verbosity=-1
            )
        except PatoolError as e:
            return Error(
                FileURLRetrievalError,
                e,
            )

        saved.unlink() # to-do: patoolib can't extract some types of archive and it won't raise an error in this case, and the archive will be deleted next. That's not what we want.


    def _handle_filedepth(self, track_dir: Path):
        pass




def main():
    logging.basicConfig( # to-do: refactor logging features.
        filename='log.txt', 
        filemode='w', 
        encoding='utf-8', 
        level=logging.INFO,
    ) 

    if len(sys.argv) == 5:
        task = Task.from_sysargv(sys.argv)
        task.run()
    else: 
        print('requires 4 arguments: event number, save_to, start, and end.')  


if __name__ == '__main__':  
    main()




# to-do: move the logging functions to a separate script.
# to-do: log the file path after gdown.download finished if the file is broken.
# patool: different MIME types detected
# inspect gdown.download parameter. Find a way (if there is one) to show only the download progress bar on terminal.
# gdown.download: The speed, callback, and log_message parameters.

# The ability to recognize and integrate different file catogories of a same song (.wav, .ogg, additional BGA file).
# Google folders
