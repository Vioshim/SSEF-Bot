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

BASE_TEMPLATES = {
    "Normal": """
# Normal Character
**Name:** 
**Job:** (Optional)
**Age:** (Optional)
**Level:** (Optional)
**Gender:** (Optional)
**Species:**  (If fusion, provide each name and types, max two.)
**Sexuality:** (Optional)
**Magic:** (Optional. Recommended for adventurers. Soft cap at 2-3 magics.)
**Equipment:** (Optional. Recommended for adventurers and those who fight often.)
## Information:
### Appearance:
**Inherit:** (Optional, only if you have Inherit. For Second Inherit, you can have 2 of these in a character.)
""".strip(),  # noqa: W291
    "Angel": """
# Angel Character

**Name:** 
**Job:** (Optional)
**Age:** (Optional)
**Level:** (Optional)
**Gender:** (Optional)
**Species:** (If fusion, provide each name and types, max two.)
**Sexuality:** (Optional)
**Magic:** (Optional. Soft cap at 2-3 magics.)
**Equipment:** (Optional. Recommended for those who fight often.)
**Embodied Virtue:** (Humility, Mercy, Kindness, Temperance, Diligence, Chastity, or Charity, can have more, it’s just what the angel’s personality embodies the most, can read the doc for more info on these. Optional)
## Information:
### Appearance:
**Inherit:** (Optional, only if you have Inherit. For Second Inherit, you can have 2 of these in a character.)
""".strip(),  # noqa: W291
    "Demon": """
# Demon Character
**Name:** 
**Job:** (Optional)
**Age:** (Optional)
**Level:** (Optional)
**Gender:** (Optional)
**Species:** (If fusion, provide each name and types, max two.)
**Sexuality:** (Optional)
**Magic:** (Optional. Soft cap at 2-3 magics.)
**Equipment:** (Optional. Recommended for those who fight often.)
**Hierarchy Rank:** (Greater Demon, Lesser Demon, and Imp, check Heaven and Hell info for more information on these)
**Sin District:** (Pride, Greed, Lust, Envy, Gluttony, Wrath, Sloth, or none, again, Heaven and Hell info, in the doc)
## Information:
### Appearance:
### Disguised Appearance:
**Inherit:** (Optional, only if you have Inherit. For Second Inherit, you can have 2 of these in a character.)
""".strip(),  # noqa: W291
}


class Sheet(StrEnum):
    Normal = auto()
    Angel = auto()
    Demon = auto()

    @property
    def template(self) -> str:
        return BASE_TEMPLATES[self.name]
