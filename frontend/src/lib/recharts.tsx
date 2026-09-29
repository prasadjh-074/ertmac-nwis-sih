// recharts 3 turned Tooltip from a generic class, `Tooltip<TValue, TName>`, into a plain function fixed
// to `TooltipProps<ValueType, NameType>`, and its formatter now receives `TValue | undefined`. On
// recharts 2 (what every tutorial and model learned) the `(v: number) =>` formatter and
// `(label: string) =>` labelFormatter an agent writes inferred their type parameters; on 3.x they fail
// TS2322 under strictFunctionTypes. Vite and tsconfig alias "recharts" here: everything from the real
// package, plus Tooltip declared with recharts 2's generic callback signatures. Nothing changes at
// runtime (as on 2.x, a missing datum still reaches the formatter as undefined). Raw package:
// "recharts-upstream".
/* oxlint-disable react/only-export-components -- `export *` re-exports upstream components */
import type { ReactNode } from "react";
import {
  Tooltip as UpstreamTooltip,
  type TooltipPayloadEntry,
  type TooltipProps as UpstreamTooltipProps,
  type TooltipValueType,
} from "recharts-upstream";

export * from "recharts-upstream";

type NameType = string | number;
type UpstreamProps = UpstreamTooltipProps<TooltipValueType, NameType>;
type TooltipPayload = Parameters<NonNullable<UpstreamProps["labelFormatter"]>>[1];

/** recharts 2's Formatter: `value` is `TValue`, inferred from the callback the caller writes. */
export type TooltipFormatter<TValue extends TooltipValueType = TooltipValueType, TName extends NameType = NameType> = (
  value: TValue,
  name: TName,
  item: TooltipPayloadEntry,
  index: number,
  payload: TooltipPayload,
) => ReactNode | [ReactNode, ReactNode];

export function Tooltip<
  TValue extends TooltipValueType = TooltipValueType,
  TName extends NameType = NameType,
  TLabel = ReactNode,
>(
  props: Omit<UpstreamTooltipProps<TValue, TName>, "formatter" | "labelFormatter"> & {
    formatter?: TooltipFormatter<TValue, TName>;
    labelFormatter?: (label: TLabel, payload: TooltipPayload) => ReactNode;
  },
) {
  // The type parameters only narrow what the callbacks declare; recharts 2 erased them the same way.
  return <UpstreamTooltip {...(props as UpstreamProps)} />;
}
