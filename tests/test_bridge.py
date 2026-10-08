from tests.conftest import unix_socket
from tuxcast import bridge


def test_links_the_snap_socket_where_clients_look(fake_system, runtime):
    system = fake_system(snaps=("discord",))
    server = unix_socket(runtime / "snap.discord/discord-ipc-0")
    try:
        links = bridge.plan(system)
        assert [(link.path.name, link.target) for link in links] == [
            ("discord-ipc-0", runtime / "snap.discord/discord-ipc-0")]
        assert links[0].path.parent == runtime / "app/com.discordapp.Discord"

        assert bridge.apply(links) == links
        assert links[0].path.readlink() == links[0].target
        assert bridge.apply(links) == []  # idempotent
    finally:
        server.close()


def test_links_lazily_when_discord_is_not_running(fake_system, runtime):
    links = bridge.plan(fake_system(snaps=("discord",)))
    assert [link.target for link in links] == [runtime / "snap.discord/discord-ipc-0"]


def test_official_flatpak_needs_no_link_and_pushes_others_up(fake_system):
    system = fake_system(snaps=("discord",), flatpaks=("com.discordapp.Discord",))
    links = bridge.plan(system)
    assert [link.path.name for link in links] == [f"discord-ipc-{bridge.FIRST_FREE_INDEX}"]


def test_never_replaces_a_real_socket(runtime):
    server = unix_socket(runtime / "app/com.discordapp.Discord/discord-ipc-0")
    try:
        links = [bridge.Link(runtime / "app/com.discordapp.Discord/discord-ipc-0",
                             runtime / "snap.discord/discord-ipc-0", bridge.VARIANTS[1])]
        assert bridge.apply(links) == []
        assert bridge.is_socket(links[0].path)
    finally:
        server.close()


def test_snap_and_flatpak_launchers_are_not_native_installs(fake_system):
    assert not bridge.native_discord(fake_system(commands={"discord": "/snap/bin/discord"}))
    assert not bridge.native_discord(fake_system(
        commands={"discord": "/var/lib/flatpak/exports/bin/discord"}))
    assert bridge.native_discord(fake_system(commands={"discord": "/usr/bin/discord"}))


def test_grant_command():
    link = bridge.Link(None, None, bridge.VARIANTS[1])  # type: ignore[arg-type]
    assert bridge.grant_command("com.core447.StreamController", [link]) == [
        "flatpak", "override", "--user", "--filesystem=xdg-run/app/com.discordapp.Discord:create",
        "--filesystem=xdg-run/snap.discord", "com.core447.StreamController"]
