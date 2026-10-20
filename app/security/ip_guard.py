import ipaddress
import json
import logging
import time
from typing import Dict, List, Set, Any
from app.config import DATA_DIR

logger = logging.getLogger("visionxr.ipguard")
IP_RULES_FILE = DATA_DIR / "ip_rules.json"

DEFAULT_WHITELIST = [
    "127.0.0.1",
    "127.0.0.22",
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16"
]

class IPGuard:
    def __init__(self):
        self.whitelist: List[str] = DEFAULT_WHITELIST.copy()
        self.blacklist: List[str] = []
        self.banned_ips: Dict[str, float] = {} # ip -> ban_expiry
        self.request_counts: Dict[str, List[float]] = {}
        self.threats_blocked = 0
        self.load_rules()

    def load_rules(self):
        if IP_RULES_FILE.exists():
            try:
                with open(IP_RULES_FILE, "r") as f:
                    data = json.load(f)
                    self.whitelist = data.get("whitelist", DEFAULT_WHITELIST)
                    self.blacklist = data.get("blacklist", [])
            except Exception as e:
                logger.error(f"Error loading IP rules: {e}")
        else:
            self.save_rules()

    def save_rules(self):
        try:
            with open(IP_RULES_FILE, "w") as f:
                json.dump({
                    "whitelist": self.whitelist,
                    "blacklist": self.blacklist
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving IP rules: {e}")

    def is_ip_in_list(self, ip_str: str, cidr_list: List[str]) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
            for item in cidr_list:
                if "/" in item:
                    net = ipaddress.ip_network(item, strict=False)
                    if addr in net:
                        return True
                else:
                    if addr == ipaddress.ip_address(item):
                        return True
        except ValueError:
            pass
        return False

    def is_allowed(self, ip_str: str) -> Dict[str, Any]:
        now = time.time()

        # Whitelist / loopback unconditionally allowed (bypass rate-limit bans)
        if self.is_ip_in_list(ip_str, self.whitelist):
            if ip_str in self.banned_ips:
                del self.banned_ips[ip_str]
            return {
                "allowed": True,
                "trusted": True,
                "status": "TRUSTED"
            }

        # Check temporary auto-bans
        if ip_str in self.banned_ips:
            if now < self.banned_ips[ip_str]:
                self.threats_blocked += 1
                return {"allowed": False, "reason": "IP temporarily banned for security violation", "status": "BANNED"}
            else:
                del self.banned_ips[ip_str]

        # Check explicit blacklist
        if self.is_ip_in_list(ip_str, self.blacklist):
            self.threats_blocked += 1
            return {"allowed": False, "reason": "IP explicitly blacklisted by Security Policy", "status": "BLACKLISTED"}

        # Rate limiting check: max 120 req / 5s
        timestamps = self.request_counts.get(ip_str, [])
        timestamps = [t for t in timestamps if (now - t) < 5.0]
        timestamps.append(now)
        self.request_counts[ip_str] = timestamps

        if len(timestamps) > 120:
            self.banned_ips[ip_str] = now + 300.0 # Ban 5 mins
            self.threats_blocked += 1
            logger.warning(f"IP {ip_str} auto-banned for rate flood violation.")
            return {"allowed": False, "reason": "Rate flood threshold exceeded: auto-banned for 5 minutes", "status": "RATE_LIMITED"}

        is_trusted = self.is_ip_in_list(ip_str, self.whitelist)
        return {
            "allowed": True,
            "trusted": is_trusted,
            "status": "TRUSTED" if is_trusted else "EXTERNAL"
        }

    def add_whitelist(self, cidr_or_ip: str):
        if cidr_or_ip not in self.whitelist:
            self.whitelist.append(cidr_or_ip)
            self.save_rules()

    def remove_whitelist(self, cidr_or_ip: str):
        if cidr_or_ip in self.whitelist:
            self.whitelist.remove(cidr_or_ip)
            self.save_rules()

    def add_blacklist(self, cidr_or_ip: str):
        if cidr_or_ip not in self.blacklist:
            self.blacklist.append(cidr_or_ip)
            self.save_rules()

    def remove_blacklist(self, cidr_or_ip: str):
        if cidr_or_ip in self.blacklist:
            self.blacklist.remove(cidr_or_ip)
            self.save_rules()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "whitelist_count": len(self.whitelist),
            "blacklist_count": len(self.blacklist),
            "active_bans_count": len(self.banned_ips),
            "threats_blocked": self.threats_blocked,
            "whitelist": self.whitelist,
            "blacklist": self.blacklist,
            "banned_ips": list(self.banned_ips.keys())
        }

ip_guard = IPGuard()
