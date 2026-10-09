#! /usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Created on Tue May 25 21:13:22 2021

@author: luonairui
"""

from __future__ import absolute_import, annotations

import dataclasses as dc, io, logging, typing as tp
import pandas as pf

from functools import lru_cache
from typing_extensions import override

from . import Resource, ResourceTransformerProto, MemoryStorage, ReferenceStorage


TableFormatType: tp.TypeAlias = tp.Literal["JSON", "CSV", "TSV", "XML", "HTML"]

logger: logging.Logger = logging.getLogger(name=__name__)


@dc.dataclass(frozen=True)
class Table(ResourceTransformerProto):
	r"""
	Table class for processing tables.
	"""

	FormatType : tp.ClassVar[type] = tp.Optional[TableFormatType]

	table       : pf.DataFrame
	resource_id : str
	metadata    : tp.Mapping[str, tp.Any]      = dc.field(default_factory=dict, kw_only=True)
	format      : tp.Optional[TableFormatType] = "JSON"

	@override
	@classmethod
	def load(cls, resource: Resource) -> tp.Self:
		storage: ReferenceStorage = resource.get(storage_type=ReferenceStorage)
		table = tp.cast(pf.DataFrame, storage.ref)
		return cls(table=table, resource_id=resource.name, metadata=resource.metadata)._resolve()

	@override
	def dump(self) -> Resource:
		if self.format is None:
			return ReferenceStorage(ref=self.table).to_resource(
				self.resource_id,
				mime_type='application/dataframe', metadata=self.metadata,
			)

		buf = io.StringIO()

		match self.format:
			case "JSON" : self.table.to_json(buf, orient="records", double_precision=4, force_ascii=False, lines=True)
			case "CSV"  : self.table.to_csv(buf, index=False, float_format='%.3f')
			case "TSV"  : self.table.to_csv(buf, sep='\t', index=False, float_format='%.3f')
			case "XML"  : self.table.to_xml(buf, index=False)
			case "HTML" : self.table.to_html(buf, index=False, float_format='%.3f')
			case _      : tp.assert_never(self.format)

		return MemoryStorage(content=buf.getvalue().encode()).to_resource(
			f'{self.resource_id}.dump({self.format!r})',
			mime_type=f'text/{self.format.lower()}', metadata=self.metadata,
		)

	@override
	def as_format(self, format: tp.Optional[TableFormatType]) -> tp.Self:
		return dc.replace(self, format=format)

	def _resolve(self) -> tp.Self:
		return dc.replace(
			self,
			metadata={
				**self.metadata,
				'shape': self._get_dim(),
				'columns': self._get_columns(),
				'dtypes': self._get_dtypes(),
			},
		)

	def get(
		self,
		format: tp.Optional[TableFormatType] = None,
	) -> str:
		r"""读取完整表格。"""

		ret = self.as_format(format or self.format)
		assert ret.format is not None
		return ret.dump().get(storage_type=MemoryStorage).content.decode()

	def _get_dim(self) -> tuple[int, int]:
		r"""Get the number of rows and columns of the table."""

		return self.table.shape

	def _get_columns(self) -> list[str]:
		return self.table.columns.tolist()

	def _get_dtypes(self) -> tp.Mapping[str, str]:
		r"""Get data types by column of the table."""

		return self.table.dtypes.astype("string").to_dict()

	def _get_description(self) -> tp.Mapping[str, str]:
		r"""获取面向人和 LLM 的数据表的描述。"""
		r"""Get the description of the table, for human and LLM."""

		return self.metadata["description"]

	def _get_explanation(self) -> tp.Mapping[str, str]:
		r"""获取面向人和 LLM 的表的每个列的定义和解释。"""
		r"""Get explanations by column of the table, for human and LLM."""

		return self.metadata["explanation"]

	def _select(self, columns: list[str]) -> tp.Self:
		r"""按列筛选数据。"""
		r"""Select partial columns of the table."""

		return dc.replace(
			self,
			table=self.table[columns],
			resource_id=(self.resource_id + f'.select({columns!r})'),
		)._resolve()

	def _sample(self, n: int = 5) -> tp.Self:
		n = min(n, len(self.table))
		return dc.replace(
			self,
			table=self.table.sample(n=n),
			resource_id=(self.resource_id + f'.sample({n!r})'),
		)._resolve()

	def _query(self, expr: str) -> tp.Self:
		r"""通过 pandas 的 query 方法按行筛选数据。"""
		r"""Apply pandas query expression to filter rows of the table."""

		return dc.replace(
			self,
			table=self.table.query(expr),
			resource_id=(self.resource_id + f'.query({expr!r})'),
		)._resolve()


if __name__ == '__main__':
	from . import global_resource_repo
	from ..session import session_context

	logging.basicConfig(level=logging.INFO)

	table = pf.DataFrame(data={'x': [1, 2], 'y': ['z', None]})
	with session_context():
		resource = ReferenceStorage(ref=table).to_resource(
			'table',
			mime_type='application/dataframe',
		)
		table = Table.load(resource)
		resource = table._query('x == 2').as_format(None).dump()
		print(resource.name)
		print(global_resource_repo.get(resource.name).get(storage_type=ReferenceStorage).ref)
		table = Table.load(resource)
		resource = table.dump()
		print(resource.name)
		print(global_resource_repo.get(resource.name).get(storage_type=MemoryStorage).content)
