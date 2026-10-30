"""Turning a twin run into the numbers an officer reads.

Definitions (all MODELLED):

* **delay** (vehicle-hours): in every cell and step, the PCU that free flow
  would have moved on but the model could not (``n - outflow / (vf dt/dx)``),
  summed over time; plus time spent waiting to enter from side streets and
  on virtual cross streets.
* **queue** (m): the delayed PCU on a link laid end to end at jam density
  over the link's lanes.
* **spill-back** (min): time during which the queue on an approach reaches
  its upstream end (its first cell is congested), so it can block the
  junction behind it.
* **cross-street delay**: delay on the approaches served by the cross
  movement at the focus junctions, including virtual cross streets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sajag_twin.ctm import Compiled, RunResult

__all__ = ["Focus", "candidate_metrics", "compare", "series_for"]


@dataclass
class Focus:
    junction_ids: list[int] = field(default_factory=list)
    corridor_links: list[int] = field(default_factory=list)

    def approach_links(self, cp: Compiled) -> list[int]:
        out: list[int] = []
        for jid in self.junction_ids:
            out += cp.net.junctions[jid].in_links
        for li in self.corridor_links:
            if li not in out:
                out.append(li)
        return out

    def labelled(self, cp: Compiled) -> tuple[list[int], list[int]]:
        """(through-like links, cross links) among the focus approaches."""
        through, cross = [], []
        corridor = set(self.corridor_links)
        for li in self.approach_links(cp):
            j = cp.net.junctions[cp.net.links[li].to_j]
            lab = j.approach_label.get(li)
            if li in corridor or lab is None or lab != "cross":
                through.append(li)
            else:
                cross.append(li)
        return through, cross

    def vx(self, cp: Compiled) -> list[int]:
        js = set(self.junction_ids)
        if self.corridor_links:
            js |= {cp.net.links[li].to_j for li in self.corridor_links}
        return [x for x in range(cp.X) if int(cp.vx_junction[x]) in js]

    def cross_links(self, cp: Compiled) -> list[int]:
        """Cross approaches at every junction in focus (incl. corridor junctions)."""
        js = set(self.junction_ids) | {cp.net.links[li].to_j for li in self.corridor_links}
        corridor = set(self.corridor_links)
        out = []
        for jid in sorted(js):
            j = cp.net.junctions[jid]
            for li in j.in_links:
                if li not in corridor and j.approach_label.get(li) == "cross":
                    out.append(li)
        return out


def _r(x: float, nd: int = 1) -> float:
    return float(round(float(x), nd))


def candidate_metrics(cp: Compiled, res: RunResult, k: int, focus: Focus) -> dict:
    net = cp.net
    appr = focus.approach_links(cp)
    through, _ = focus.labelled(cp)
    cross = focus.cross_links(cp)
    vx = focus.vx(cp)
    H = 3600.0
    net_delay = (res.link_delay_vs[k].sum() + res.link_entry_delay_vs[k].sum() + res.vx_delay_vs[k].sum()) / H
    focus_delay = (res.link_delay_vs[k, appr].sum() + res.vx_delay_vs[k, vx].sum()) / H
    cross_delay = (res.link_delay_vs[k, cross].sum() + res.vx_delay_vs[k, vx].sum()) / H
    through_delay = res.link_delay_vs[k, through].sum() / H
    q_links = res.link_max_queue_m[k, appr] if appr else np.zeros(0)
    q_vx = res.vx_max_queue_m[k, vx] if vx else np.zeros(0)
    max_q = float(max([0.0, *q_links.tolist(), *q_vx.tolist()]))
    spill_focus = float(res.link_spill_s[k, appr].sum() / 60.0) if appr else 0.0
    spill_net = float(res.link_spill_s[k].sum() / 60.0)
    cross_max_q = float(max([0.0, *res.link_max_queue_m[k, cross].tolist(), *q_vx.tolist()]))
    served = float(res.link_out_veh[k, appr].sum() + res.vx_out_veh[k, vx].sum())
    approaches = []
    for li in appr:
        l = net.links[li]
        j = net.junctions[l.to_j]
        approaches.append(
            {
                "link_id": l.link_id,
                "road_name": l.road_name,
                "from_junction": l.from_j,
                "junction_id": l.to_j,
                "movement": j.approach_label.get(li),
                "delay_veh_h": _r(res.link_delay_vs[k, li] / H, 1),
                "max_queue_m": _r(res.link_max_queue_m[k, li], 0),
                "mean_queue_m": _r(res.link_mean_queue_m[k, li], 0),
                "spillback_min": _r(res.link_spill_s[k, li] / 60.0, 1),
                "length_m": _r(l.length_m, 0),
            }
        )
    for x in vx:
        jid = int(cp.vx_junction[x])
        approaches.append(
            {
                "link_id": f"virtual-cross:{jid}",
                "road_name": "cross street (virtual: not in the network)",
                "from_junction": None,
                "junction_id": jid,
                "movement": "cross",
                "delay_veh_h": _r(res.vx_delay_vs[k, x] / H, 1),
                "max_queue_m": _r(res.vx_max_queue_m[k, x], 0),
                "mean_queue_m": None,
                "spillback_min": None,
                "length_m": None,
            }
        )
    return {
        "network_delay_veh_h": _r(net_delay, 1),
        "focus_delay_veh_h": _r(focus_delay, 1),
        "through_delay_veh_h": _r(through_delay, 1),
        "cross_street_delay_veh_h": _r(cross_delay, 1),
        "max_queue_m": _r(max_q, 0),
        "cross_street_max_queue_m": _r(cross_max_q, 0),
        "spillback_min": _r(spill_focus, 1),
        "network_spillback_min": _r(spill_net, 1),
        "served_pcu": _r(served, 0),
        "exited_pcu": _r(res.exited_veh[k], 0),
        "approaches": approaches,
    }


def _pct(new: float, old: float) -> float:
    if abs(old) < 1e-6:
        return 0.0 if abs(new) < 1e-6 else 100.0
    return (new - old) / old * 100.0


def compare(cand: dict, base: dict) -> dict:
    """Signed changes of a candidate against do-nothing (negative = better)."""
    return {
        "delay_change_pct": _r(_pct(cand["focus_delay_veh_h"], base["focus_delay_veh_h"]), 1),
        "network_delay_change_pct": _r(_pct(cand["network_delay_veh_h"], base["network_delay_veh_h"]), 1),
        "cross_street_delay_change_pct": _r(_pct(cand["cross_street_delay_veh_h"], base["cross_street_delay_veh_h"]), 1),
        "max_queue_change_m": _r(cand["max_queue_m"] - base["max_queue_m"], 0),
        "max_queue_change_pct": _r(_pct(cand["max_queue_m"], base["max_queue_m"]), 1),
        "cross_street_max_queue_change_m": _r(cand["cross_street_max_queue_m"] - base["cross_street_max_queue_m"], 0),
        "spillback_change_min": _r(cand["spillback_min"] - base["spillback_min"], 1),
        "network_spillback_change_min": _r(cand["network_spillback_min"] - base["network_spillback_min"], 1),
        "served_change_pcu": _r(cand["served_pcu"] - base["served_pcu"], 0),
    }


def series_for(cp: Compiled, res: RunResult, k: int, focus: Focus) -> dict:
    """Queue time series (m, one point per minute) of the focus approaches."""
    out: dict = {"t_min": [_r(t, 1) for t in res.series_t_min.tolist()], "queue_m": {}, "network_delayed_pcu": []}
    for li in focus.approach_links(cp):
        out["queue_m"][cp.net.links[li].link_id] = [_r(v, 0) for v in res.series_link_queue_m[k, :, li].tolist()]
    for x in focus.vx(cp):
        out["queue_m"][f"virtual-cross:{int(cp.vx_junction[x])}"] = [_r(v, 0) for v in res.series_vx_queue_m[k, :, x].tolist()]
    out["network_delayed_pcu"] = [_r(v, 0) for v in res.series_delayed_veh[k].tolist()]
    return out
