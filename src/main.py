from abc import ABC, abstractmethod
from typing import Dict, List, Iterable


class Player:
    def __init__(self, name: str, start_cash: int, position: "Space"):
        self.name = name
        self.cash = start_cash
        self.portfolio: Dict[Purchasable, int] = {}
        self.has_jail_free_card = False
        self.position = position

    def __hash__(self):
        return hash(self.name)

    def buy_stock(self, space: "Purchasable", num_shares: int) -> bool:
        max_poss_buy = 100
        if space in self.portfolio:
            max_poss_buy -= self.portfolio[space]
        if 0 >= num_shares >= max_poss_buy:
            raise ValueError
        cost = space.get_stock_price(num_shares)
        if cost > self.cash:
            return False
        self.cash -= cost
        space.sell_stock(self, num_shares)
        if space not in self.portfolio:
            self.portfolio[space] = 0
        self.portfolio[space] += num_shares
        return True

    def sell_stock(self, space: "Purchasable", num_shares: int) -> bool:
        if space not in self.portfolio or num_shares > self.portfolio[space]:
            return False
        space.buy_stock(self, num_shares)
        self.portfolio[space] -= num_shares
        self.cleanup()

    def cleanup(self) -> None:
        for space in self.portfolio:
            if self.portfolio[space] == 0:
                del self.portfolio[space]

    def do_request(self, query: str, poss_answers: Iterable[str]) -> str:
        while (answer := input(f"{self.name}: {query}\n")) not in poss_answers:
            print("Invalid answer. Answer must be one of:")
            print(poss_answers)
        return answer


class Space(ABC):
    def __init__(self, name: str, board: "Board", prev_space: "Space" = None, next_space: "Space" = None):
        self.name = name
        self.num_players: int = 0
        self.board = board
        self.prev = prev_space
        self.next = next_space
        self.residents: List[Player] = []


class Purchasable(ABC, Space):
    def __init__(self, name: str, company: "Company", total_stock_value: int, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(Purchasable, self).__init__(name, board, prev_space, next_space)
        self.total_stock_value = total_stock_value
        self.owners: Dict[Player, int] = {}
        self.unowned_stock: int = 100
        self.company = company

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
        sold_shares_cost = self.total_stock_value * num_shares // 100
        self.company.funds -= sold_shares_cost
        self.owners[seller] -= num_shares
        self.cleanup()

    def cleanup(self, do_company_cleanup: bool = True) -> None:
        for player in self.owners:
            if self.owners[player] == 0:
                del self.owners[player]
        if (owned := sum(self.owners.values())) < 100:
            self.unowned_stock = 100 - owned
        if do_company_cleanup:
            self.company.cleanup()

    @abstractmethod
    def get_rent(self) -> int:
        ...

    @abstractmethod
    def foreclose(self) -> None:
        ...


class Property(Purchasable):
    def __init__(self, name: str, company: "Company", total_stock_value: int, rent_prices: List[int], board: "Board", prev_space: Space = None, next_space: Space = None):
        super(Property, self).__init__(name, company, total_stock_value, board, prev_space, next_space)
        self.num_houses = 0
        self.rent_array = rent_prices

    def get_rent(self) -> int:
        return self.rent_array[self.num_houses]

    def foreclose(self) -> None:
        self.num_houses = 0
        for owner in self.owners:
            del owner.portfolio[self]
        self.owners = {}
        self.unowned_stock = 100


class Railroad(Purchasable):
    def __init__(self, name: str, company: "Company", total_stock_value: int, rent_prices: List[int], board: "Board", prev_space: Space = None, next_space: Space = None):
        super(Railroad, self).__init__(name, company, total_stock_value, board, prev_space, next_space)
        self.rent_array = rent_prices
        self.majority_owner: Player | None = None

    def get_rent(self) -> int:
        count = 1
        if self.majority_owner is not None:
            count = sum((asset.majority_owner == self.majority_owner for asset in self.company.assets))
        return self.rent_array[count]

    def foreclose(self) -> None:
        self.majority_owner = None
        self.owners = {}
        self.unowned_stock = 100

    def cleanup(self) -> None:
        super(Railroad, self).cleanup()
        for owner in self.owners:
            if self.owners[owner] > 50:
                self.majority_owner = owner
                break


class Utility(Purchasable):
    def __init__(self, name: str, company: "Company", total_stock_value: int, rent_multipliers: List[int], board: "Board", prev_space: Space = None, next_space: Space = None):
        super(Utility, self).__init__(name, company, total_stock_value, board, prev_space, next_space)
        self.rent_mult = rent_multipliers
        self.majority_owner: Player | None = None

    def get_rent(self, roll: int) -> int:
        count = 1
        if self.majority_owner is not None:
            count = sum((asset.majority_owner == self.majority_owner for asset in self.company.assets))
        return self.rent_mult[count] * roll

    def foreclose(self) -> None:
        self.majority_owner = None
        self.owners = {}
        self.unowned_stock = 100

    def cleanup(self) -> None:
        super(Utility, self).cleanup()
        for owner in self.owners:
            if self.owners[owner] > 50:
                self.majority_owner = owner
                break


class Company:
    def __init__(self, name: str, assets: List[Purchasable], starting_funds: int):
        self.name = name
        self.assets = assets
        self.funds = starting_funds
        self.owners: Dict[Player, int] = {}
        for asset in assets:
            for owner in asset.owners:
                if owner not in self.owners:
                    self.owners[owner] = 0
                self.owners[owner] += asset.owners[owner]

    def cleanup(self) -> None:
        for asset in self.assets:
            asset.cleanup(False)
            for owner in asset.owners:
                if owner not in self.owners:
                    self.owners[owner] = 0
                self.owners[owner] += asset.owners[owner]
        if self.funds < 0:
            added_funds = 0
            for owner in self.owners:
                query_string = f"Company {self.name} is {-self.funds} in debt. How much money do you want to give to keep it afloat?"
                answer = int(owner.do_request(query_string, map(str, range(0, owner.cash + 1))))
                owner.cash -= answer
                added_funds += answer
            self.funds += added_funds
            if self.funds < 0:
                self.foreclose()

    def foreclose(self) -> None:
        self.funds = 0
        self.owners = {}
        for asset in self.assets:
            asset.foreclose()


class ActionSpace(ABC, Space):
    def __init__(self, name: str, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(ActionSpace, self).__init__(name, board, prev_space, next_space)

    @abstractmethod
    @property
    def pass_action(self) -> bool:
        ...

    @abstractmethod
    def do_action(self, player: Player) -> None:
        ...


class GoSpace(Space):
    def __init__(self, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(GoSpace, self).__init__("GO", board, prev_space, next_space)

    @property
    def pass_action(self) -> bool:
        return True

    @staticmethod
    def do_action(player: Player) -> None:
        player.cash += 200


class ChanceSpace(Space):
    def __init__(self, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(ChanceSpace, self).__init__("CHANCE", board, prev_space, next_space)

    @property
    def pass_action(self) -> bool:
        return False

    def do_action(self, player: Player) -> None:
        self.board.draw_chance(player)


class CommunityChestSpace(Space):
    def __init__(self, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(CommunityChestSpace, self).__init__("COMMUNITY CHEST", board, prev_space, next_space)

    @property
    def pass_action(self) -> bool:
        return False

    def do_action(self, player: Player) -> None:
        self.board.draw_community_chest(player)


class TaxSpace(Space):
    def __init__(self, name: str, tax_amount: List[int | float], board: "Board", prev_space: Space = None, next_space: Space = None):
        super(TaxSpace, self).__init__(name, board, prev_space, next_space)
        self.amount_array = tax_amount

    @property
    def pass_action(self) -> bool:
        return True

    def do_action(self, player: Player) -> None:
        poss_payments = []
        for amount in self.amount_array:
            if type(amount) == int:
                poss_payments.append(amount)
                continue
            poss_payments.append(amount * player.cash)
        final_tax_amount = min(poss_payments)
        player.cash -= final_tax_amount
        self.board.free_parking.cash += final_tax_amount


class JailSpace(Space):
    def __init__(self, board: "Board", next_space: Space = None):
        super(JailSpace, self).__init__("JAIL", board, None, next_space)


class FreeParkingSpace(ActionSpace):
    def __init__(self, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(FreeParkingSpace, self).__init__("FREE PARKING", board, prev_space, next_space)
        self.cash = 0

    @property
    def pass_action(self, player: Player) -> bool:
        return False

    def do_action(self, player: Player) -> None:
        player.cash += self.cash
        self.cash = 0


class GoToJailSpace(ActionSpace):
    def __init__(self, jail_space: JailSpace, board: "Board", prev_space: Space = None, next_space: Space = None):
        super(GoToJailSpace, self).__init__("GO TO JAIL", board, prev_space, next_space)
        self.jail_space = jail_space
