import logging
from typing import List, Optional, Pattern

from .custom_textwrap import CustomTextWrap

logger = logging.getLogger(__name__)


async def break_into_groups(text: Optional[str] = None, heading: str = "", template: str = "```python\n",
                            ending: str = "\n```", line_template: str = "", lines: Optional[List[str]] = None,
                            regex: Optional[Pattern[str]] = None) -> List[str]:
    if text is None:
        text = ""
    lines = [line.replace("```", "``​`") for line in (text.splitlines(False) if not lines else lines)]
    return_lines = []
    msg = "{}{}".format(heading, template)
    allocation = 1024 - len(template + ending)
    while lines:
        line = lines.pop(0)
        if len(line) > allocation:  # Special case
            width = (allocation - len(msg) - len(line_template) - 2)
            if width < 5:
                width = 5
            textwrap = CustomTextWrap(regex=regex, width=width, break_on_hyphens=False,
                                      replace_whitespace=False)
            extra_lines = textwrap.wrap(line)
            lines = extra_lines + lines
            continue
        newmsg = msg + (line if not line_template else line_template.format(line)) + "\n"
        if len(newmsg.rstrip()) > allocation:
            return_lines.append(msg.rstrip() + ending)
            msg = template + (line if not line_template else line_template.format(line)) + "\n"
        else:
            msg = newmsg
    if msg:
        return_lines.append(msg.rstrip() + ending)
    return return_lines
