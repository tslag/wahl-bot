import os
from pathlib import Path

from config.config import settings
from core.logging import logger
from db.session import AsyncSessionLocal
from fastapi import UploadFile
from models.programs import Program
from sqlalchemy import select, text


class ProgramStore:

    def __init__(self):
        self.program_dir = (
            Path(__file__).parent.parent.parent.parent / settings.PROGRAM_DIRECTORY
        )
        self.program_dir.mkdir(exist_ok=True)  # Ensure directory exists
        logger.debug("ProgramStore initialized, program_dir=%s", self.program_dir)

    async def get_program(self, program_name: str) -> Program | None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Program).filter(Program.name == program_name)
            )
            program: Program | None = result.scalars().first()
            if program:
                logger.debug(
                    "Found program in DB name=%s id=%s",
                    program_name,
                    getattr(program, "id", None),
                )
            else:
                logger.debug("Program not found in DB name=%s", program_name)
            return program

    async def list_programs(self) -> list[Program]:
        stmt = text("SELECT * FROM programs")

        async with AsyncSessionLocal() as db:
            result = await db.execute(stmt)
            programs = []
            rows = result.fetchall()
            for row in rows:
                program = Program(
                    id=row.id,
                    name=row.name,
                    # session_id=row.session_id,
                    created_at=row.created_at,
                )
                programs.append(program)
            return programs
            logger.debug("Listed %d programs", len(programs))

    async def safe_program(self, program_name: str, file_content: UploadFile) -> Path:

        if await self.get_program(program_name):
            logger.info("Program %s already exists.", program_name)
            return True

        # Create a sanitized filename
        safe_program_name = "".join(
            c for c in program_name if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        file_extension = os.path.splitext(file_content.filename)[1]

        # Create target file path
        file_path = self.program_dir / f"{safe_program_name}{file_extension}"

        # Save the file
        try:
            logger.info(
                "Saving program file %s to %s", file_content.filename, file_path
            )
            with open(file_path, "wb") as f:
                f.write(file_content.file.read())
            logger.info("Saved program file %s", file_path)
        except Exception:
            logger.exception(
                "Failed to save program file %s to %s", file_content.filename, file_path
            )
            raise

        # create db entry for program
        async with AsyncSessionLocal() as db:
            # Get program info from ProgramStore later
            db_program = Program(
                name=program_name,
            )
            db.add(db_program)
            await db.commit()
            logger.info(
                "Created program DB entry name=%s id=%s",
                program_name,
                getattr(db_program, "id", None),
            )
            return db_program

        return True

    async def delete_program(self, program_name: str) -> bool:

        if not await self.get_program(program_name):
            logger.info("Program %s does not exist", program_name)
            return False

        logger.info("Deleting program %s from db..", program_name)
        stmt = text("DELETE FROM programs WHERE name = :program_name")

        async with AsyncSessionLocal() as db:
            await db.execute(stmt, {"program_name": program_name})
            await db.commit()
            logger.info("Deleted program record from DB name=%s", program_name)

        logger.info("Deleting program %s from file store..", program_name)
        safe_program_name = "".join(
            c for c in program_name if c.isalnum() or c in (" ", "-", "_")
        ).strip()

        # Search for files with the given program name (any extension)
        deleted_files = 0
        for file in self.program_dir.glob(f"{safe_program_name}.*"):
            try:
                file.unlink()
                deleted_files += 1
                logger.debug("Deleted program file %s", file)
            except Exception:
                logger.exception("Failed to delete program file %s", file)
        logger.info("Deleted %d files for program %s", deleted_files, program_name)

        return True
