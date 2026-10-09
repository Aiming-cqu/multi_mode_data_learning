#! /usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Created on Tue May 25 21:13:22 2021

@author: luonairui
"""

from __future__ import absolute_import, annotations

import inspect, types, typing as tp
import logfire

from functools import update_wrapper
from pydantic_ai import RunContext, ModelRetry
from pydantic_ai.toolsets import FunctionToolset, PrefixedToolset

from . import Resource, ResourceTransformerProto
from .image import Image
from .table import Table
from .video import Video
from ..session import SessionIdType, SessionContextManager


def get_callable_name(func: tp.Callable) -> str:
	if attr := getattr(func, '__name__', None): return attr
	if attr := getattr(func, 'func', None): return get_callable_name(attr)
	return str(func)


class ResourceDepsProto(tp.Protocol):
	session_id: SessionIdType


ResourceDepsT = tp.TypeVar('ResourceDepsT', bound=ResourceDepsProto)


def wrap_transformer(cls: type[ResourceTransformerProto]) -> FunctionToolset[ResourceDepsProto]:
	def wrap_method(func):
		func_name: str = get_callable_name(func)
		sig_old: inspect.Signature = inspect.signature(func)
		type_hints_old: tp.Mapping[str, tp.Any] = tp.get_type_hints(func)

		if type_hints_old['return'] is tp.Self:
			def wrapper(
				ctx: RunContext[ResourceDepsT], id: str,
				*args,
				out_format: tp.Any = cls.format,
				**kwds
			) -> str:
				with logfire.span(
					'Run transform {func_name}: session={session}, '
					'id={id}, out_format={out_format}, args={args}, kwds={kwds}',
					func_name=func_name, session=ctx.deps.session_id,
					id=id, out_format=out_format,
					args=args, kwds=kwds
				):
					with SessionContextManager(ResourceContext()):
						try:
							resource: Resource = Resource.repo().get(id)
							obj: ResourceTransformerProto = cls.load(resource)
							obj = func(obj, *args, **kwds)
							ret = obj.as_format(out_format).dump().id
						except (Exception, ) as exc:
							logfire.exception(f'error in {func_name}: {exc!r}')
							raise ModelRetry(repr(exc)) from exc
						logfire.info(f'return: {ret!r}')
						return ret
			sig_new: inspect.Signature = inspect.signature(wrapper)
			type_hints_new: tp.Mapping[str, tp.Any] = tp.get_type_hints(wrapper)
			update_wrapper(wrapper, func)
			param_new = list(sig_new.parameters.values())
			wrapper.__signature__ = sig_new.replace(parameters=(
				param_new[:2] + list(sig_old.parameters.values())[1:] + [param_new[3]]
			))
			wrapper.__annotations__['return'] = str
			wrapper.__annotations__['out_format'] = cls.FormatType
		else:
			return_type_new: type = type_hints_old['return']
			is_return_type_resource: bool = issubclass(type_hints_old['return'], Resource)
			if is_return_type_resource: return_type_new = str
			def wrapper(
				ctx: RunContext[ResourceDepsT], id: str,
				*args, **kwds
			) -> str:
				with logfire.span(
					'Run transform {func_name}: session={session}, '
					'id={id}, args={args}, kwds={kwds}',
					func_name=func_name, session=ctx.deps.session_id,
					id=id, args=args, kwds=kwds
				):
					with SessionContextManager(ResourceContext()):
						try:
							resource: Resource = Resource.repo().get(id)
							obj: ResourceTransformerProto = cls.load(resource)
							ret = func(obj, *args, **kwds)
							if is_return_type_resource: ret = ret.id
						except (Exception, ) as exc:
							logfire.exception(f'error in {func_name}: {exc!r}')
							raise ModelRetry(repr(exc)) from exc
						logfire.info(f'return: {ret!r}')
						return ret
			sig_new: inspect.Signature = inspect.signature(wrapper)
			type_hints_new: tp.Mapping[str, tp.Any] = tp.get_type_hints(wrapper)
			update_wrapper(wrapper, func)
			param_new = list(sig_new.parameters.values())
			wrapper.__signature__ = sig_new.replace(parameters=(
				param_new[:2] + list(sig_old.parameters.values())[1:]
			))
			wrapper.__annotations__['return'] = return_type_new
		wrapper.__annotations__['ctx'] = type_hints_new['ctx']
		wrapper.__annotations__['id'] = type_hints_new['id']

		logfire.info(
			f'wrapped transform {func_name}',
			sig_old=sig_old, sig_new=wrapper.__signature__,
			ann_old=type_hints_old, ann_new=wrapper.__annotations__,
		)
		return wrapper

	tools = list[tp.Callable]()
	names_to_skip = set[str](dir(ResourceTransformerProto))
	for name in dir(cls):
		if name.startswith('_'): continue
		if name in names_to_skip: continue
		attr: tp.Any = getattr(cls, name)
		if not isinstance(attr, types.FunctionType): continue
		tools.append(wrap_method(attr))

	return FunctionToolset[ResourceDepsProto](tools=tools)


image_toolset = PrefixedToolset[ResourceDepsProto](wrap_transformer(Image), prefix='image')
table_toolset = PrefixedToolset[ResourceDepsProto](wrap_transformer(Table), prefix='table')
video_toolset = PrefixedToolset[ResourceDepsProto](wrap_transformer(Video), prefix='video')


if __name__ == '__main__':
	pass
