from core.preset import Preset, Variable


class AppState:
    def __init__(self) -> None:
        self.preset = Preset()

    def replace_preset(
        self,
        variables: list[Variable],
        name: str | None,
    ) -> tuple[bool, str | None]:
        try:
            self.preset = Preset(variables=variables, name=name)
        except Exception as exc:
            return False, str(exc)
        return True, None

    def load_preset(self, preset: Preset) -> None:
        self.preset = preset
