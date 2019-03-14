from core import Core


class EventTriggerProvider:
    def __init__(self, rule, engine):
        self.rule = rule
        self.engine = engine
        self.core = engine.core

        self.data = rule.data["trigger"]
        self.event_data = self.data.get("data", {})


        # Subscribe to trigger event
        event(self.data["type"])(self.on_event)

    async def on_event(self, event, **kwargs):

        if self.event_data.items() <= kwargs.items():
            await self.rule.on_trigger(kwargs)
        

class StateActionProvider:
    def __init__(self, rule, engine):
        self.engine = engine
        self.rule = rule
        self.core = engine.core

        self.data = rule.data["action"]

    async def on_trigger(self, data):
        target = self.core.entity_manager.items.get(self.data["target"])
        changes = {**self.data.get("data", {}), **{key: data.get(ref) for key, ref in self.data.get("var-data", {}).items()}}

        if self.core.start_args.get("verbose"):
            print("STATE ACTION by automation", changes, target)

        for state, value in changes.items():
            await target.states.set(state, value)


class Module:
    core: Core

    async def init(self):
        self.trigger_providers = {
            "event": EventTriggerProvider
        }
        self.condition_providers = {
            
        }
        self.action_providers = {
            "state": StateActionProvider
        }
        self.rules = set()

        for rule in self.core.cfg.get("automation", []):
            self.rules.add(AutomationRule(rule, self))

class AutomationRule:
    def __init__(self, data, engine: Module):
        self.data = data
        self.engine = engine
        self.core = engine.core
        self.alias = data.get("alias", "Unnamed")

        self.trigger = self.engine.trigger_providers[data["trigger"]["provider"]](self, self.engine)
        self.action = self.engine.action_providers[data["action"]["provider"]](self, self.engine)

    async def on_trigger(self, data):
        await self.action.on_trigger(data)