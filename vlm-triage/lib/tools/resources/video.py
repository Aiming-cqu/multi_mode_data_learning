#! /usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Created on Tue May 25 21:13:22 2021

@author: luonairui
"""

from __future__ import absolute_import, annotations

import dataclasses as dc, json, logging, subprocess, typing as tp

from functools import lru_cache
from typing_extensions import override

from . import (
	Resource, ResourceTransformerProto, FileStorage,
	
)


BoxType: tp.TypeAlias = tuple[int, int, int, int]  # (left, top, right, bottom)


VideoFormatType: tp.TypeAlias = tp.Literal["MP4"]

logger: logging.Logger = logging.getLogger(name=__name__)


@dc.dataclass(frozen=True, slots=True)
class VideoMeta:
	width    : int
	height   : int
	duration : float
	fps      : float

	@classmethod
	@lru_cache()
	def load(cls, source: str) -> tp.Self:
		args = [
			'ffprobe',
			'-hide_banner',
			'-of', 'json',
			'-show_format', '-show_streams',
			source,
		]
		logger.info('run ffprobe with: %r', args)
		out = json.loads(subprocess.check_output(args))
		stream: tp.Mapping[str, tp.Any] = next(
			s for s in out["streams"] if s["codec_type"] == "video")
		return cls(
			width=stream["width"],
			height=stream["height"],
			duration=float(stream["duration"]),
			fps=(int(stream["nb_frames"]) / float(stream["duration"])),
		)


@dc.dataclass(frozen=True)
class Video(ResourceTransformerProto):
	r"""
	Video class for processing videos.
	"""

	FormatType : tp.ClassVar[type] = VideoFormatType

	DEFAULT_ARGS: tp.ClassVar[list[tp.LiteralString]] = \
		'-c:v libx264 -crf 21 -preset fast -tune animation -an'.split()  #  -movflags faststart

	resource   : Resource
	format     : VideoFormatType    = "MP4"
	start_time : tp.Optional[float] = None
	end_time   : tp.Optional[float] = None
	fps        : tp.Optional[float] = None
	vf         : str                = ''

	@override
	@classmethod
	def load(cls, resource: Resource) -> tp.Self:
		return cls(resource=resource)

	@override
	def dump(self) -> Resource:
		resource_id: str = self.resource.name

		args = list[str](self.DEFAULT_ARGS)
		if self.start_time is not None:
			args = ['-ss', f'{self.start_time:.1f}'] + args
			resource_id += f'/ss={self.start_time:.1f}'
		if self.end_time is not None:
			args = ['-to', f'{self.end_time:.1f}'] + args
			resource_id += f'/to={self.end_time:.1f}'
		if self.fps is not None:
			args = ['-r', f'{self.fps:.1f}'] + args
			resource_id += f'/fps={self.fps:.1f}'
		if self.vf:
			args = args + ['-vf', self.vf]
			resource_id += f'/vf={self.vf}'

		try: return Resource.repo().get(resource_id)
		except (KeyError, ): pass

		path: str = FileStorage.make_path(resource_id, self.format.lower())
		args = [
			'ffmpeg',
			'-hide_banner',
			'-y',
			'-i', self.resource.get(storage_type=FileStorage).path,
			*args,
			path,
		]
		logger.info('run ffmpeg with: %r', args)
		subprocess.check_call(args)

		return FileStorage(path=path).to_resource(
			resource_id,
			mime_type=f'video/{self.format.lower()}',
			metadata={**self.resource.metadata, **dc.asdict(VideoMeta.load(path))},
		)

	@override
	def as_format(self, format: VideoFormatType) -> tp.Self:
		return dc.replace(self, format=format)

	def get_source_meta(self) -> VideoMeta:
		return VideoMeta.load(self.resource.get(storage_type=FileStorage).path)

	def trim(
		self,
		start_time: tp.Optional[float] = None, end_time: tp.Optional[float] = None,
	) -> tp.Self:
		kwds = dict()
		if end_time is not None:
			kwds["end_time"] = (self.start_time or 0) + end_time
		if start_time is not None:
			kwds["start_time"] = (self.start_time or 0) + start_time
		return dc.replace(self, **kwds)

	def _resample(self, fps: float) -> tp.Self:
		return dc.replace(self, fps=fps)

	def filter(self, vf: str) -> tp.Self:
		r"""Apply ffmpeg video filter."""

		return dc.replace(self, vf=((self.vf + ',' if self.vf else '') + vf))

	def _resize(self, size: tuple[int, int]) -> tp.Self:
		w, h = size
		return self.filter(f'scale={w}:{h}')

	def _crop(self, box_xyxy: BoxType) -> tp.Self:
		l, t, r, b = self._normalize_box(box_xyxy)
		return self.filter(f'crop={r - l}:{b - t}:{l}:{t}')

	def equalize(self) -> tp.Self:
		return self.filter('eq=contrast=1.0:brightness=0.05:saturation=1.5')

	def capture(self, time: float) -> Resource:
		r"""Capture frame at time point, return the caputred image ID"""

		resource_id: str = f'{self.resource.name}/capture={time:.1f}'
		path: str = FileStorage.make_path(resource_id, 'jpg')
		args = [
			'ffmpeg',
			'-hide_banner',
			'-y',
			'-i', self.resource.get(storage_type=FileStorage).path,
			'-ss', f'{time:.1f}',
			'-frames:v', '1',
			path,
		]
		logger.info('run ffmpeg with: %r', args)
		subprocess.check_call(args)

		meta: VideoMeta = self.get_source_meta()
		return FileStorage(path=path).to_resource(
			resource_id,
			mime_type='image/jpeg',
			metadata={**self.resource.metadata, 'width': meta.width, 'height': meta.height},
		)

	def _normalize_box(self, box_xyxy: BoxType) -> BoxType:
		l, t, r, b = box_xyxy
		meta: VideoMeta = self.get_source_meta()
		l, r = max(0, l), min(meta.width, r)
		t, b = max(0, t), min(meta.height, b)
		return (l, t, r, b)


if __name__ == '__main__':
	from . import HTTPStorage, global_resource_repo
	from ..session import session_context

	logging.basicConfig(level=logging.INFO)

	video_url = 'https://s3-nmg-inter.didistatic.com/orion-nmg-cn/all_data/ares_animation_videos/task_2100094100000060_0.mp4'
	with session_context():
		resource = HTTPStorage(url=video_url).to_resource('animation')
		video = Video.load(resource)
		resource = video._crop((568, 0, 1920, 810)).dump()
		print(resource.name)
		print(global_resource_repo.get(resource.name).get(storage_type=FileStorage).path)
		resource = video.capture(0.5)
		print(resource.name)
		print(global_resource_repo.get(resource.name).get(storage_type=FileStorage).path)
