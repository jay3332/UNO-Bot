from __future__ import annotations

import discord
import random

from discord.ext import commands
from dataclasses import dataclass
from typing import Iterable, Literal, NamedTuple, Union, overload

from .cards import Card, create_deck


@dataclass
class RuleSet:
    stacking: bool = True
    progressive: bool = True
    seven_o: bool = False
    jump_in: bool = False


class RuleSetChoice(NamedTuple):
    name: str
    description: str = 'No description provided.'


class HostOnlyView(discord.ui.View):
    def __init__(self, host: discord.Member, *, timeout: float = 360) -> None:
        super().__init__(timeout=timeout)
        self._view_owner: discord.Member = host

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.user != self._view_owner:
            await interaction.response.send_message(
                'You are not the host of this game.', ephemeral=True
            )
            return False
        return True


class RuleSetPrompt(discord.ui.Select['RuleSetPromptingView']):
    CHOICES = {
        'stacking': RuleSetChoice(
            'Stacking',
            'Allows the play of multiple cards that have the same value/type at once.'
        ),
        'progressive': RuleSetChoice(
            'Progressive',
            'Draw cards can be progressively stacked until one must draw.'
        ),
        'seven_o': RuleSetChoice(
            'Seven-O',
            'If you play a 7, you can swap hands. When a 0 is played, everyone passes their hands to their left.'
        ),
        'jump_in': RuleSetChoice(
            'Jump In',
            'Immediately play a card that is a duplicate of the current card, even if it isn\'t your turn.'
        )
    }

    def __init__(self, game: UNO) -> None:
        self.game: UNO = game

        super().__init__(
            min_values=0,
            max_values=len(self.CHOICES),
            options=[
                discord.SelectOption(
                    label=v.name,
                    value=k,
                    description=v.description,
                    default=getattr(self.game.rule_set, k, False)
                )
                for k, v in self.CHOICES.items()
            ],
            placeholder='Select game rules...'
        )

    async def callback(self, interaction: discord.Interaction, /) -> None:
        values = interaction.data['values']
        for value in self.CHOICES:
            setattr(self.game.rule_set, value, value in values)

        await interaction.response.defer()


class RuleSetPromptingView(HostOnlyView):
    def __init__(self, game: UNO) -> None:
        super().__init__(game.host, timeout=360)
        self.add_item(RuleSetPrompt(game))
        self.game: UNO = game

    @discord.ui.button(label='Continue', style=discord.ButtonStyle.success, row=1)
    async def _continue(self, _button: discord.ui.Button, _interaction: discord.Interaction, /) -> None:
        await self.game.queue_players()


class PlayerQueueingView(discord.ui.View):
    OPENING_MESSAGE = (
        'Click the "Join" button to join this UNO game.\n'
        'Starting in 3 minutes, or if 10 players join.\n'
        'The host can also start early.'
    )

    def __init__(self, game: UNO) -> None:
        self.game: UNO = game
        self.players: set[discord.Member] = game.players
        game.players.add(self.game.host)  # Just in case

        self.immediate_start_button: discord.ui.Button = discord.ui.Button(
            label='Start!',
            style=discord.ButtonStyle.primary,
            disabled=True
        )

        async def _(interaction: discord.Interaction, /) -> None:
            if interaction.user != self.game.host:
                return await interaction.response.send_message(
                    'Only the host can start this game.',
                    ephemeral=True
                )

            if len(self.players) < 2:
                return await interaction.response.send_message(
                    'There must be at least 2 players in order to start this game.',
                    ephemeral=True
                )

            self.stop()

        self.immediate_start_button.callback = _

        super().__init__(timeout=180)
        self.add_item(self.immediate_start_button)

    async def _update(self) -> None:
        self.immediate_start_button.disabled = len(self.players) > 1

        await self.game._send(
            self.OPENING_MESSAGE + '\n\n**Players:**\n' + '\n'.join(
                str(player) for player in self.players
            ),
            view=self
        )

    @discord.ui.button(label='Join', style=discord.ButtonStyle.green)
    async def join(self, _: discord.ui.Button, interaction: discord.Interaction) -> None:
        if interaction.user in self.players:
            return await interaction.response.send_message(
                'You are already in this game.',
                ephemeral=True
            )

        self.players.add(interaction.user)
        await self._update()

    @discord.ui.button(label='Leave', style=discord.ButtonStyle.red)
    async def leave(self, _: discord.ui.Button, interaction: discord.Interaction) -> None:
        if interaction.user not in self.players:
            return await interaction.response.send_message(
                'You are not in this game.',
                ephemeral=True
            )

        if interaction.user == self.game.host:
            return await interaction.response.send_message(
                'You cannot leave this game as you are the host.',
                ephemeral=True
            )

        self.players.remove(interaction.user)
        await self._update()


class DeckView(discord.ui.View):
    # This will be sent ephemerally, so
    # user checks won't be needed

    def __init__(self) -> None:
        super().__init__(timeout=None)


class GameView(discord.ui.View):
    def __init__(self, game: UNO) -> None:
        super().__init__(timeout=None)
        self.game: UNO = game

    @discord.ui.button(label='View deck')
    async def view_deck(self, _: discord.ui.Button, interaction: discord.Interaction) -> None:
        ...


class Deck:
    def __init__(self, game: UNO) -> None:
        self._internal_deck: list[Card] = []
        self.game: UNO = game
        self.reset()

    def __repr__(self) -> str:
        return f'<Deck cards={len(self)}>'

    def __len__(self) -> int:
        return len(self._internal_deck)

    def __iter__(self) -> Iterable[Card]:
        return iter(self._internal_deck)

    def shuffle(self) -> None:
        random.shuffle(self._internal_deck)

    def pop(self) -> Card:
        return self._internal_deck.pop(0)

    def reset(self) -> None:
        self._internal_deck = create_deck()


class Hand:
    def __init__(self, game: UNO, player: discord.Member) -> None:
        self.game: UNO = game
        self.player: discord.Member = player
        self._cards: list[Card] = []

    def __repr__(self) -> str:
        return f'<Hand player={self.player!r} cards={len(self)}>'

    def __len__(self) -> int:
        return len(self._cards)

    def _draw_one(self) -> Card:
        card = self.game.deck.pop()
        self._cards.append(card)
        return card

    @overload
    def draw(self, amount: Literal[1] = 1, /) -> Card:
        ...

    def draw(self, amount: int = 1, /) -> Union[list[Card], Card]:
        if amount == 1:
            return self._draw_one()

        return [self._draw_one() for _ in range(amount)]

    @staticmethod
    def _card_sort_key(card: Card, /) -> tuple[int, int, int]:
        return card.color.value, card.type.value, card.value or 0

    @property
    def cards(self) -> list[Card]:
        return sorted(self._cards, key=self._card_sort_key)


class UNO:
    def __init__(
        self,
        ctx: commands.Context,
        *,
        host: discord.Member = None,
        rule_set: RuleSet = None,
        players: Iterable[discord.Member] = ()
    ) -> None:
        self.ctx: commands.Context = ctx
        self.host: discord.Member = host or ctx.author

        self.rule_set: RuleSet = rule_set  # This could be None on init
        self.players: set[discord.Member] = set(players)

        self.deck: Deck = Deck(self)
        self.hands: list[Hand] = []  # This will also determine order
        self.current: Card = None
        self.turn: int = 0

        self._message: discord.Message = None

    def __repr__(self) -> str:
        return f'<UNO players={len(self.players)} turn={self.turn} rule_set={self.rule_set!r}>'

    @property
    def current_hand(self) -> Hand:
        return self.hands[self.turn]

    @property
    def current_player(self) -> discord.Member:
        return self.current_hand.player

    def get_hand(self, user: discord.Member, /) -> Hand:
        return discord.utils.get(self.hands, player=user)

    async def _send(self, content: str = None, **kwargs) -> discord.Message:
        if self._message is None:
            self._message = res = await self.ctx.send(content, **kwargs)
            return res

        await self._message.edit(content=content, **kwargs)
        return self._message

    async def _resend(self, content: str = None, **kwargs) -> discord.Message:
        await self._message.delete()
        return await self._send(content, **kwargs)

    async def choose_rule_set(self) -> None:
        self.rule_set = RuleSet()
        content = f'{self.host.mention}, choose the game rules you would like to use.'
        await self._send(content=content, view=RuleSetPromptingView(self))

    async def queue_players(self) -> None:
        view = PlayerQueueingView(self)
        await self._send(content=PlayerQueueingView.OPENING_MESSAGE, view=view)
        await view._update()
        await view.wait()

        self.players = view.players

    def _deal_cards(self) -> None:
        for hand in self.hands:
            hand.draw(7)

    async def _run_initial_prompts(self) -> None:
        await self.choose_rule_set()
        self.hands = [Hand(self, player) for player in self.players]
        random.shuffle(self.hands)

    def _setup(self) -> None:
        self.deck.shuffle()
        self.current = self.deck.pop()
        self._deal_cards()

    async def start(self) -> None:
        await self._run_initial_prompts()
        self._setup()
