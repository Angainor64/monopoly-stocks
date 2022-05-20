from abc import ABC, abstractmethod
from typing import Dict, List


class Player:
    def __init__(self, name: str, start_cash: int):
        self.name = name
        self.cash = start_cash
        self.stocks_owned: Dict[Purchasable, int] = {}

    def __hash__(self):
        return hash(self.name)

    def buy_stock(self, space: "Purchasable", num_shares: int) -> bool:
        max_poss_buy = 100
        if space in self.stocks_owned:
            max_poss_buy -= self.stocks_owned[space]
        if 0 >= num_shares >= max_poss_buy:
            raise ValueError
        cost = space.get_stock_price(num_shares)
        if cost > self.cash:
            return False
        self.cash -= cost
        space.sell_stock(self, num_shares)
        if space not in self.stocks_owned:
            self.stocks_owned[space] = 0
        self.stocks_owned[space] += num_shares
        return True

    def sell_stock(self, space: "Purchasable", num_shares: int) -> bool:
        if space not in self.stocks_owned or num_shares > self.stocks_owned[space]:
            return False
        space.buy_stock(self, num_shares)
        self.stocks_owned[space] -= num_shares
        self.cleanup()

    def cleanup(self) -> None:
        for space in self.stocks_owned:
            if self.stocks_owned[space] == 0:
                del self.stocks_owned[space]

    def do_request(self, query: str, poss_answers: List[str]) -> str:
        while (answer := input(f"{self.name}: {query}\n")) not in poss_answers:
            print("Invalid answer. Answer must be one of:")
            print(poss_answers)
        return answer


class Space(ABC):
    def __init__(self, name: str, prev_space: "Space" = None, next_space: "Space" = None):
        self.name = name
        self.num_players: int = 0
        self.prev = prev_space
        self.next = next_space

    @abstractmethod
    def get_action(self):
        """
        The action that must be taken by the player when landing on this space
        :return: Uhhhhh... an "Action" object, maybe? I'll figure this out later
        """
        ...


class Purchasable(ABC, Space):
    def __init__(self, name: str, company: Company, total_stock_value: int, prev_space: Space = None, next_space: Space = None):
        super(Purchasable, self).__init__(name, prev_space, next_space)
        self.total_stock_value = total_stock_value
        self.owners: Dict[Player, int] = {}
        self.unowned_stock: int = 100

    def get_stock_price(self, num_shares: int) -> int:
        return self.total_stock_value * num_shares // 100

    def sell_stock(self, buyer: Player, num_shares: int) -> None:
        if buyer not in self.owners:
            self.owners[buyer] = 0
        self.owners[buyer] += num_shares
        if self.unowned_stock >= num_shares:
            self.unowned_stock -= num_shares
            return
        if self.unowned_stock:
            num_shares -= self.unowned_stock
            self.unowned_stock = 0
        sellers = self.owners.copy()
        del sellers[buyer]
        total_leftover = 0
        for seller in sellers:
            bought_shares, leftover = divmod(sellers[seller] * num_shares, 100)
            self.owners[seller] -= bought_shares
            total_leftover += leftover
        for seller in sellers:
            if total_leftover == 0:
                return
            if self.owners[seller] > 0:
                self.owners[seller] -= 1
                total_leftover -= 1
        self.cleanup()

    def buy_stock(self, seller: Player, num_shares: int) -> None:
        pass

    def cleanup(self) -> None:
        for player in self.owners:
            if self.owners[player] == 0:
                del self.owners[player]
        if (owned := sum(self.owners.values())) < 100:
            self.unowned_stock = 100 - owned
