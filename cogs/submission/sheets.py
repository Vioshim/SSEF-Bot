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


class Sheet(StrEnum):
    Empty = auto()
    Pocket = auto()

    @property
    def template(self):
        match self:
            case Sheet.Empty:
                return (
                    "Brotherhood:\n"
                    "Job:\n"
                    "Age:\n"
                    "Level:\n"
                    "Gender:\n"
                    "Species:\n"
                    "Sexuality:\n"
                    "Magic:\n"
                    "Equipment:\n"
                    "Information:\n"
                    "Appearance:\n"
                    "Inherit:\n"
                    "Stats:\n"
                    "HP:\n"
                    "Atk:\n"
                    "SpAtk:\n"
                    "Def:\n"
                    "SpDef:\n"
                    "Spe:"
                )
            case _:
                return "Age:\nGender:\nInfo:\nAppearance:"
