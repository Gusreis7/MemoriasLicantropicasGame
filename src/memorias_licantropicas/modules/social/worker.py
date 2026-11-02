"""Worker cancelável. Leitura HTTP não executa inferência social."""

import asyncio
import logging

from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError

logger = logging.getLogger(__name__)


class SocialWorker:
    def __init__(self, service, repository, interval_seconds=1):
        if interval_seconds <= 0:
            raise ValueError("Intervalo do worker deve ser positivo.")
        self._service = service
        self._repository = repository
        self._interval = interval_seconds
        self._task = None

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="social-worker")

    async def stop(self):
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def run_once(self):
        for game_id in await self._repository.active_game_ids():
            try:
                await self._service.tick(game_id)
            except (ConflictError, NotFoundError):
                # Jogador tem prioridade; uma partida encerrada pode sair do índice entre leituras.
                continue
            except Exception:
                # Não registrar textos privados, prompts ou payloads de provedores.
                logger.warning("Uma tarefa social falhou; será reavaliada no próximo ciclo.")

    async def _run(self):
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Worker social aguardando recuperação da persistência.")
            await asyncio.sleep(self._interval)
