# Copyright 2023 Vioshim
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from enum import StrEnum, auto

BASE_TEMPLATE = """
**Name:** 
**Job:** (Optional)
**Age:** (Optional)
**Level:** (Optional)
**Gender:** 
**Species:** 
**Sexuality:** (Optional)
**Magic:** (Optional. Recommended for adventurers. Soft cap at 2-3 magics.)
**Equipment:** (Optional. Recommended for adventurers and those who fight often.)

**Information:** 

**Appearance:** 

**Inherit:** (Optional, only if you have Inherit. For Second Inherit, you can have 2 of these in a character.)

**Stats:** (Optional)
- **Health:** 3/5
- **Attack:** 3/5
- **Special Attack:** 3/5
- **Defense:** 3/5
- **Special Defense:** 3/5
- **Speed:** 3/5

**Equipment Sheet:**
- [Type+Specialty?] **[Name Here]:** Enchant Here, Name if Any, and Explanation. Max 3 Enchants per character.
""".strip()  # noqa: W291


class Sheet(StrEnum):
    Empty = auto()
    Pocket = auto()

    @property
    def template(self):
        match self:
            case Sheet.Empty:
                items = [
                    "Job",
                    "Age",
                    "Level",
                    "Gender",
                    "Species",
                    "Sexuality",
                    "Magic",
                    "Equipment",
                    "Information",
                    "Appearance",
                    "Inherit",
                    "Stats",
                    "HP",
                    "Atk",
                    "SpAtk",
                    "Def",
                    "SpDef",
                    "Spe",
                ]
            case _:
                items = [
                    "Age",
                    "Gender",
                    "Info",
                    "Appearance",
                ]
        return "\n".join(f"{item}: " for item in items)
