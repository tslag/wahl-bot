from pathlib import Path

import jinja2
from core.logging import logger


def get_prompt(path: str):
    prompt_template_path = Path(path)
    if not prompt_template_path.is_absolute():
        backend_dir = Path(__file__).resolve().parent.parent.parent
        prompt_template_path = backend_dir / path

    prompt_template_loader = jinja2.FileSystemLoader(
        searchpath=str(prompt_template_path.parent)
    )
    prompt_template_env = jinja2.Environment(loader=prompt_template_loader)
    try:
        prompt_template = prompt_template_env.get_template(prompt_template_path.name)
        rendered = prompt_template.render()
        logger.debug("Loaded prompt template %s", prompt_template_path)
        return rendered
    except Exception:
        logger.exception("Failed to load prompt template %s", prompt_template_path)
        raise
