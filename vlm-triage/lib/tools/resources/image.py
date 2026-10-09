#! /usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Created on Tue May 25 21:13:22 2021

@author: luonairui
"""

from __future__ import absolute_import, annotations

import dataclasses as dc, io, logging, typing as tp
import PIL.Image
import PIL.ImageDraw
import PIL.ImageOps

from functools import lru_cache
from typing_extensions import override

from . import Resource, ResourceTransformerProto, MemoryStorage

BoxType: tp.TypeAlias = tuple[int, int, int, int]  # (left, top, right, bottom)



ImageFormatType: tp.TypeAlias = tp.Literal["JPEG", "PNG"]

logger: logging.Logger = logging.getLogger(name=__name__)


@dc.dataclass(frozen=True)
class Image(ResourceTransformerProto):
	r"""
	Image class for processing images.
	"""

	DRAW_COLOR : tp.ClassVar[str] = "red"
	DRAW_WIDTH : tp.ClassVar[int] = 2

	FormatType : tp.ClassVar[type] = ImageFormatType

	image       : PIL.Image.Image
	resource_id : str
	metadata    : tp.Mapping[str, tp.Any] = dc.field(default_factory=dict, kw_only=True)
	format      : ImageFormatType         = "JPEG"

	@override
	@classmethod
	def load(cls, resource: Resource) -> tp.Self:
		content: bytes = resource.get(storage_type=MemoryStorage).content
		return cls(
			image=PIL.Image.open(io.BytesIO(content)),
			resource_id=resource.name, metadata=resource.metadata,
		)._resolve()

	@override
	def dump(self) -> Resource:
		buf = io.BytesIO()
		self.image.save(buf, format=self.format)
		return MemoryStorage(content=buf.getvalue()).to_resource(
			self.resource_id,
			mime_type=f'image/{self.format.lower()}', metadata=self.metadata,
		)

	@override
	def as_format(self, format: ImageFormatType) -> tp.Self:
		return dc.replace(self, format=format)

	def _resolve(self) -> tp.Self:
		width, height = self._get_size()  # type: int, int
		return dc.replace(
			self,
			metadata={**self.metadata, 'width': width, 'height': height},
		)

	def _get_size(self) -> tuple[int, int]:
		return self.image.size

	def _resize(self, size: tuple[int, int]) -> tp.Self:
		width, height = size  # type: int, int
		return dc.replace(
			self,
			image=self.image.resize(size),
			resource_id=(self.resource_id + f'.resize({size!r})'),
			metadata={**self.metadata, 'width': width, 'height': height},
		)

	def _crop(self, box_xyxy: BoxType)  -> tp.Self:
		l, t, r, b = box_xyxy = self._normalize_box(box_xyxy)
		return dc.replace(
			self,
			image=self.image.crop(box_xyxy),
			resource_id=(self.resource_id + f'.crop({box_xyxy!r})'),
			metadata={**self.metadata, 'width': r - l, 'height': b - t},
		)

	def equalize(self) -> tp.Self:
		return dc.replace(
			self,
			image=PIL.ImageOps.equalize(self.image),
			resource_id=(self.resource_id + '.equalize()'),
		)

	def _draw_point(self, point: tuple[int, int]) -> tp.Self:
		x, y = point
		w, h = self._get_size()
		assert 0 <= x < w and 0 <= y < h, 'Point out of bounds'
		image: PIL.Image.Image = self.image.copy()
		draw = PIL.ImageDraw.Draw(image)
		draw.circle(point, self.DRAW_WIDTH, fill=self.DRAW_COLOR)
		return dc.replace(
			self,
			image=image,
			resource_id=(self.resource_id + f'.draw_point({point!r})'),
		)

	def _draw_box(
		self, box_xyxy: BoxType,
	) -> tp.Self:
		box_xyxy = self._normalize_box(box_xyxy)
		image: PIL.Image.Image = self.image.copy()
		draw = PIL.ImageDraw.Draw(image)
		draw.rectangle(box_xyxy, outline=self.DRAW_COLOR, width=self.DRAW_WIDTH)
		return dc.replace(
			self,
			image=image,
			resource_id=(self.resource_id + f'.draw_box({box_xyxy!r})'),
		)

	def _normalize_box(self, box_xyxy: BoxType) -> BoxType:
		l, t, r, b = box_xyxy
		w, h = self._get_size()
		l, r = max(0, l), min(w, r)
		t, b = max(0, t), min(h, b)
		return (l, t, r, b)


if __name__ == '__main__':
	from . import FileStorage, HTTPStorage, global_resource_repo
	from ..session import session_context

	logging.basicConfig(level=logging.INFO)

	image_url = 'https://s3-gz01.didistatic.com/pillars-uc/didi/user/jobCard/144115188103150121/1HU9xP9IPHWllHY17aQn8zz7vhpPn1pW.jpg'
	with session_context():
		resource = HTTPStorage(url=image_url).to_resource('avatar')
		image = Image.load(resource)
		resource = image._draw_box((10, 10, 90, 90)).dump()
		print(resource.name)
		print(global_resource_repo.get(resource.name).get(storage_type=FileStorage).path)
