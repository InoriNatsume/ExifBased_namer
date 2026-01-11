from tests import _bootstrap  # noqa: F401

import unittest

from core.adapters.nais import export_variable_to_nais
from core.preset import Variable, VariableValue


class ImportExportTests(unittest.TestCase):
    def test_export_rejects_empty_tags(self) -> None:
        variable = Variable(
            name="Emotion",
            values=[VariableValue(name="a", tags=[])],
        )
        with self.assertRaises(ValueError):
            export_variable_to_nais(variable)


if __name__ == "__main__":
    unittest.main()
