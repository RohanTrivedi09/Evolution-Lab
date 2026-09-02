from __future__ import annotations
import copy, math, random, time
from dataclasses import dataclass
from typing import Callable
from .models import Dataset, Weights


@dataclass(frozen=True)
class Session:
    id: str; course_id: str; name: str; faculty_id: str; group_ids: tuple[str, ...]; room_type: str


@dataclass
class Assignment:
    day: int; period: int; room: str

    def copy(self): return Assignment(self.day, self.period, self.room)


@dataclass
class Score:
    total_cost: float; normalized_fitness: float; hard_violations: int; soft_violations: int
    group_gaps: int; daily_fragmentation: int; violation_details: list[dict]

    def as_dict(self): return self.__dict__


class Problem:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset
        self.rooms = {r.id: r for r in dataset.rooms}
        self.faculty = {f.id: f for f in dataset.faculty}
        self.groups = {g.id: g for g in dataset.groups}
        self.sessions = [Session(f"{c.id}-{n}", c.id, c.name, c.faculty_id, tuple(c.group_ids), c.room_type)
                         for c in dataset.courses for n in range(1, c.sessions_per_week + 1)]
        self.room_ids = [r.id for r in dataset.rooms]
        self.course_preferences = {c.id: {(dataset.days.index(p.day), dataset.periods.index(p.period)) for p in c.preferred_periods
                                          if p.day in dataset.days and p.period in dataset.periods} for c in dataset.courses}

    def random_candidate(self, rng: random.Random) -> list[Assignment]:
        return [Assignment(rng.randrange(len(self.dataset.days)), rng.randrange(len(self.dataset.periods)), rng.choice(self.room_ids)) for _ in self.sessions]

    def evaluate(self, candidate: list[Assignment], weights: Weights) -> Score:
        hard = soft = gaps = fragmentation = 0; details = []
        occupied: dict[tuple[str, int, int], list[int]] = {}
        for i, (session, a) in enumerate(zip(self.sessions, candidate)):
            valid = 0 <= a.day < len(self.dataset.days) and 0 <= a.period < len(self.dataset.periods) and a.room in self.rooms
            if not valid:
                hard += 1; details.append({"session_id": session.id, "category":"domain", "message":"Assignment is outside the valid domain"}); continue
            key = (a.room, a.day, a.period)
            occupied.setdefault(key, []).append(i)
            room = self.rooms[a.room]
            if room.type != session.room_type:
                hard += 1; details.append({"session_id":session.id,"category":"room_type","message":f"Room must be {session.room_type}"})
            size = max((self.groups[g].size for g in session.group_ids), default=0)
            if room.capacity < size:
                hard += 1; details.append({"session_id":session.id,"category":"capacity","message":f"Room capacity {room.capacity} is below group size {size}"})
            unavailable = self.faculty[session.faculty_id].unavailable
            if any(x.day == self.dataset.days[a.day] and x.period == self.dataset.periods[a.period] for x in unavailable):
                hard += 1; details.append({"session_id":session.id,"category":"faculty_availability","message":"Faculty is unavailable"})
            if (a.day, a.period) in self.course_preferences.get(session.course_id, set()): soft = max(0, soft - 1)
            elif self.course_preferences.get(session.course_id): soft += 1
        for key, indexes in occupied.items():
            if len(indexes) > 1:
                for i in indexes[1:]:
                    hard += 1; details.append({"session_id":self.sessions[i].id,"category":"room_conflict","message":"Room is double-booked"})
        resources: dict[tuple[str, int, int], list[str]] = {}
        for session, a in zip(self.sessions, candidate):
            if 0 <= a.day < len(self.dataset.days) and 0 <= a.period < len(self.dataset.periods):
                for resource in [session.faculty_id, *session.group_ids]: resources.setdefault((resource,a.day,a.period), []).append(session.id)
        for (resource, _, _), ids in resources.items():
            if len(ids) > 1:
                kind = "faculty_conflict" if resource.startswith("F") else "group_conflict"
                hard += len(ids)-1; details.append({"session_id":ids[0],"category":kind,"message":f"{resource} has overlapping sessions"})
        for group in self.groups:
            by_day: dict[int, list[int]] = {}
            for session, a in zip(self.sessions, candidate):
                if group in session.group_ids and 0 <= a.day < len(self.dataset.days): by_day.setdefault(a.day, []).append(a.period)
            for periods in by_day.values():
                span = range(min(periods), max(periods)+1); gaps += len(set(span) - set(periods)); fragmentation += max(0, len(set(periods))-1)
        total = weights.hard*hard + weights.soft*soft + weights.gaps*gaps + weights.fragmentation*fragmentation
        return Score(total, 1/(1+max(0,total)), hard, soft, gaps, fragmentation, details)


@dataclass
class OptimizationResult:
    candidate: list[Assignment]; score: Score; history: list[dict]; evaluations: int; runtime_ms: float

    def as_dict(self, problem: Problem):
        schedule = {s.id:{"day":problem.dataset.days[a.day],"period":problem.dataset.periods[a.period],"room_id":a.room} for s,a in zip(problem.sessions,self.candidate)}
        return {"schedule":schedule,"score":self.score.as_dict(),"history":self.history,"evaluations":self.evaluations,"runtime_ms":round(self.runtime_ms,2)}


class Optimizer:
    def __init__(self, problem: Problem, weights: Weights, seed: int, params: dict, progress_callback: Callable | None = None):
        self.problem, self.weights, self.rng, self.params, self.progress_callback = problem, weights, random.Random(seed), params, progress_callback
        self.evaluations = 0
    def score(self, c): self.evaluations += 1; return self.problem.evaluate(c, self.weights)
    def history_point(self, iteration, score, average=None, candidate=None, **extra):
        item={"iteration":iteration,"best_cost":score.total_cost,"best_fitness":score.normalized_fitness,"hard_violations":score.hard_violations}
        if average is not None: item["average_cost"] = average
        if candidate is not None:
            item["schedule"] = {s.id:{"day":self.problem.dataset.days[a.day],"period":self.problem.dataset.periods[a.period],"room_id":a.room} for s,a in zip(self.problem.sessions,candidate)}
        item.update(extra); return item
    def emit(self, item):
        if self.progress_callback: self.progress_callback(item)
    def run(self) -> OptimizationResult: raise NotImplementedError
    def mutate(self, candidate):
        child=[a.copy() for a in candidate]; i=self.rng.randrange(len(child)); child[i]=self.problem.random_candidate(self.rng)[i]; return child
    def neighbor(self, candidate): return self.mutate(candidate)


class LocalSearch(Optimizer):
    def run(self):
        start=time.perf_counter(); iterations=int(self.params.get("iterations", self.params.get("generations", 100))); current=self.problem.random_candidate(self.rng); current_score=self.score(current); best=[a.copy() for a in current]; best_score=current_score; history=[]; temperature=float(self.params.get("initial_temperature",1000)); cooling=float(self.params.get("cooling_rate",.95)); accepted=0; accepted_moves=0; rejected_moves=0; plateaus=0; escaped=0
        for iteration in range(iterations):
            candidate=self.neighbor(current); candidate_score=self.score(candidate); delta=candidate_score.total_cost-current_score.total_cost
            probability=1.0 if delta <= 0 else math.exp(-delta/max(temperature,.0001)); accept=delta <= 0 or (self.params.get("mode")=="sa" and self.rng.random() < probability)
            if accept: current,current_score=candidate,candidate_score; accepted += int(delta > 0); accepted_moves += 1; escaped += int(self.params.get("mode")=="sa" and delta > 0)
            else: rejected_moves += 1; plateaus += int(delta == 0)
            if current_score.total_cost < best_score.total_cost: best,best_score=[a.copy() for a in current],current_score
            event=("Accepted a worse solution to escape a local optimum" if delta > 0 and accept else "Improved the current timetable" if accept else "Rejected a worse neighbor")
            point=self.history_point(iteration,best_score,candidate=best,temperature=temperature,accepted_worse_moves=accepted,current_cost=current_score.total_cost,neighbor_cost=candidate_score.total_cost,acceptance_probability=round(probability,4),accepted_moves=accepted_moves,rejected_moves=rejected_moves,plateaus=plateaus,escaped_local_optima=escaped,local_optimum_detected=rejected_moves > 4,event=event); history.append(point); self.emit(point); temperature*=cooling
        return OptimizationResult(best,best_score,history,self.evaluations,(time.perf_counter()-start)*1000)


class GeneticAlgorithm(Optimizer):
    def run(self):
        start=time.perf_counter(); generations=int(self.params.get("generations",100)); size=int(self.params.get("population_size",30)); mutation=float(self.params.get("mutation_rate",.12)); pop=[self.problem.random_candidate(self.rng) for _ in range(size)]; best=None; history=[]
        for generation in range(generations):
            scores=[self.score(c) for c in pop]; index=min(range(size),key=lambda i:scores[i].total_cost)
            if best is None or scores[index].total_cost < best[1].total_cost: best=([a.copy() for a in pop[index]],scores[index])
            point=self.history_point(generation,best[1],sum(s.total_cost for s in scores)/len(scores),candidate=best[0],population_diversity=len({tuple((a.day,a.period,a.room) for a in c) for c in pop}),generation=generation+1,population_size=size,mutation_rate=mutation,crossover_rate=float(self.params.get("crossover_rate",.8)),elite_count=1,best_individual_fitness=best[1].normalized_fitness,event="New population evaluated and elite preserved"); history.append(point); self.emit(point)
            next_pop=[best[0]]
            while len(next_pop)<size:
                parent=min(self.rng.sample(pop, min(3,len(pop))),key=lambda c:self.problem.evaluate(c,self.weights).total_cost); child=[a.copy() for a in parent]
                if self.rng.random()<mutation: child=self.mutate(child)
                next_pop.append(child)
            pop=next_pop
        return OptimizationResult(best[0],best[1],history,self.evaluations,(time.perf_counter()-start)*1000)


class ParticleSwarm(Optimizer):
    """Discrete PSO: particles move toward personal/global best through gene adoption and random mutation."""
    def run(self):
        start=time.perf_counter(); iterations=int(self.params.get("iterations",100)); size=int(self.params.get("swarm_size",20)); particles=[self.problem.random_candidate(self.rng) for _ in range(size)]; personal=[([a.copy() for a in p],self.score(p)) for p in particles]; global_best=min(personal,key=lambda x:x[1].total_cost); initial_cost=global_best[1].total_cost; history=[]
        for iteration in range(iterations):
            velocity_changes=0
            for i,p in enumerate(particles):
                for gene in range(len(p)):
                    if self.rng.random()<.35: p[gene]=global_best[0][gene].copy(); velocity_changes += 1
                    elif self.rng.random()<.25: p[gene]=personal[i][0][gene].copy(); velocity_changes += 1
                if self.rng.random()<.2: p=self.mutate(p)
                score=self.score(p)
                if score.total_cost<personal[i][1].total_cost: personal[i]=([a.copy() for a in p],score)
                if score.total_cost<global_best[1].total_cost: global_best=([a.copy() for a in p],score)
            point=self.history_point(iteration,global_best[1],sum(s.total_cost for _,s in personal)/size,candidate=global_best[0],swarm_diversity=len({tuple((a.day,a.period,a.room) for a in p) for p in particles}),particle_count=size,average_velocity=round(velocity_changes/max(1,size*len(global_best[0])),3),convergence_percentage=round(max(0,100*(1-global_best[1].total_cost/max(1,initial_cost)),),2),event="Particles attracted toward personal and global bests"); history.append(point); self.emit(point)
        return OptimizationResult(global_best[0],global_best[1],history,self.evaluations,(time.perf_counter()-start)*1000)


def optimizer_for(name, problem, weights, seed, params, progress_callback=None):
    if name == "hill_climbing": params={**params,"mode":"hc"}; return LocalSearch(problem,weights,seed,params,progress_callback)
    if name == "simulated_annealing": params={**params,"mode":"sa"}; return LocalSearch(problem,weights,seed,params,progress_callback)
    if name == "genetic_algorithm": return GeneticAlgorithm(problem,weights,seed,params,progress_callback)
    if name == "particle_swarm": return ParticleSwarm(problem,weights,seed,params,progress_callback)
    raise ValueError(name)
