from __future__ import annotations
import sys
import logging

from collections import namedtuple
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup, Tag

import re
import gdown
from pathlib import Path
import os

import patoolib


logger = logging.getLogger(__name__)


Track = namedtuple('Track', ['event', 'num', 'artists', 'team', 'title', 'size', 'addr'])

@dataclass
class Task:
    event: int 
    save_to: Path
    start: int = 1
    end: int = 999
    SITE = "https://manbow.nothing.sh/event/event.cgi?action=URLList" # 

    @classmethod
    def from_sysargv(cls, argv: list) -> Task:
        _, event, save_to, start, end = argv
        return cls(event, Path(save_to), start, end)

    def run(self):
        soup = self._fetch_html()
        has_team = self._inspect_headers(soup)
        tracks = self._get_tracks(soup, has_team)
        li = [] #
        for track in tracks:
            track_dir = self._mkdir(track)
            if len(track.addr.find_all('a')) != 1:
                li.append(track)
            for anchor in track.addr.find_all('a'):
                saved = self._download(anchor, to=track_dir)
                if saved is None:
                    continue # 
                self._extract(saved)

    def _fetch_html(self) -> BeautifulSoup:
        params = {'event':self.event, 'start':self.start, 'end':self.end}
        html = requests.get(self.SITE, params=params).content.decode('Shift_JIS')
        return BeautifulSoup(html, 'html5lib')

    def _inspect_headers(self, soup) -> bool:
        headers = [th.text for th in soup.thead.find_all('th')]
        match headers:
            case ['No', 'Name', 'Team', 'Title', 'Size', 'Addr']:
                return True # has the "team" column.
            case ['No', 'Name', 'Title', 'Size', 'Addr']:
                return False # doesn't have the "team" column. 
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
                            num.text,
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
                            num.text,
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
        name = self._validate(f'{track.num}. {track.title} (by {track.artists})')
        track_dir = self.save_to / name 
        track_dir.mkdir(parents=True, exist_ok=True)
        return track_dir

    def _validate(self, data: str) -> str: 
        if len(data) > 255:
            data = data[:255]
        return re.sub(r'[*"/\<>:|?]', '_', data)

    def _download(self, anchor: Tag, to: Path) -> str:
        patterns = {
            re.compile(r'google\.com/(?:open|file|uc|download)'): self._dl_google_file,
            re.compile(r'google\.com/drive/folders/'): self._dl_google_folder,
            re.compile(r'dropbox\.com'): self._dl_dropbox,
        }
        for pattern, download in patterns.items():
            if pattern.search(anchor['href']):
                return download(anchor, to) 
        return None #

    def _dl_google_file(self, anchor: Tag, track_dir: Path) -> Path: 
        output = str(track_dir) + os.path.sep  # gdown.download: The parameter output expects a string. If output is an existing directory or ends with a path separator, the basename will be appended automatically.
        try:
            saved = gdown.download(url=anchor['href'], output=output)
        except Exception as e:
            logger.info(e)
            return 
        print(f'{'':-^40}')
        if saved is None: raise Exception(f'saved: {saved}')
        return Path(saved)
        
    def _dl_google_folder(self, anchor: Tag, track_dir: Path) -> Path: 
        output = str(track_dir) + os.path.sep  # gdown.download_folder: The parameter output expects a string. If output is an existing directory or ends with a path separator, the basename will be appended automatically.
        try:
            saved = gdown.download_folder(url=anchor['href'], output=output) 
        except Exception as e:
            logger.info(e)
            return 
        print(f'{'':-^40}')
        if saved is None: raise Exception(f'saved: {saved}')
        return Path(saved)

    def _dl_dropbox(self, anchor: Tag, track_dir: Path) -> Path:
        url = re.sub('dl=0', 'dl=1', anchor['href'])
        output = str(track_dir) + os.path.sep  # gdown.download: The parameter output expects a string. If output is an existing directory or ends with a path separator, the basename will be appended automatically.
        try:
            saved = gdown.download(url=url, output=output)
        except:
            logger.info(e)
            return
        print(f'{'':-^40}')
        if saved is None: raise Exception(f'saved: {saved}')
        return Path(saved)

    def _extract(self, saved: Path): 
        if not patoolib.is_archive(saved): return
        try:
            patoolib.extract_archive(str(saved), outdir=str(saved.parent), interactive=False, verbosity=-1)
        except Exception as e:
            print(e) #
        saved.unlink()

    def _handle_filedepth(self, track_dir: Path):
        pass


def main():
    logging.basicConfig(filename='log.txt', filemode='w', encoding='utf-8', level=logging.DEBUG) # filename path
    if len(sys.argv) == 5:
        task = Task.from_sysargv(sys.argv)
        task.run()
    else: 
        print('requires 4 arguments: event number, save_to, start, and end.') # 

if __name__ == '__main__':  
    main()


# id
# The ability to recognize and integrate different file catogories of a same song (.wav, .ogg, additional BGA file).
# Google folders
