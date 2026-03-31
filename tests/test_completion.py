from __future__ import annotations

from pathlib import Path


def test_detect_omz_returns_custom_dir_when_env_set(monkeypatch, tmp_path):
    """当 ZSH_CUSTOM 环境变量存在时，应返回对应路径。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import detect_omz_custom_dir
    result = detect_omz_custom_dir()
    assert result == custom_dir


def test_detect_omz_returns_default_when_env_not_set_but_dir_exists(monkeypatch, tmp_path):
    """当 ZSH_CUSTOM 未设置但 ~/.oh-my-zsh/custom 存在时，应返回默认路径。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    default_dir = tmp_path / ".oh-my-zsh" / "custom"
    default_dir.mkdir(parents=True)
    from agent_kit.completion import detect_omz_custom_dir
    result = detect_omz_custom_dir(home=tmp_path)
    assert result == default_dir


def test_detect_omz_returns_none_when_no_omz(monkeypatch, tmp_path):
    """当 oh-my-zsh 环境完全不存在时，应返回 None。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import detect_omz_custom_dir
    result = detect_omz_custom_dir(home=tmp_path)
    assert result is None


def test_generate_completion_script_contains_compdef_for_agent_kit_and_ak():
    """生成的补全脚本应同时包含 agent-kit 和 ak 的 compdef 注册。"""
    from agent_kit.completion import generate_zsh_completion_script
    script = generate_zsh_completion_script()
    assert "compdef _agent-kit agent-kit" in script or "compdef _agent_kit agent-kit" in script
    assert "compdef _agent-kit ak" in script or "compdef _agent_kit ak" in script


def test_generate_completion_script_contains_complete_env_var():
    """生成的补全脚本应包含 _AGENT_KIT_COMPLETE 环境变量调用。"""
    from agent_kit.completion import generate_zsh_completion_script
    script = generate_zsh_completion_script()
    assert "_AGENT_KIT_COMPLETE" in script


def test_generate_completion_script_has_compdef_header():
    """生成的补全脚本应以 #compdef 开头。"""
    from agent_kit.completion import generate_zsh_completion_script
    script = generate_zsh_completion_script()
    assert script.startswith("#compdef ")


def test_install_omz_creates_plugin_dir_and_files(monkeypatch, tmp_path):
    """oh-my-zsh 安装模式应创建 _agent-kit 和 agent-kit.plugin.zsh 两个文件。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion
    result = install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    assert (plugin_dir / "_agent-kit").exists()
    assert (plugin_dir / "agent-kit.plugin.zsh").exists()
    assert result.method == "omz"


def test_install_omz_plugin_zsh_contains_fpath_and_compdef(monkeypatch, tmp_path):
    """oh-my-zsh 插件入口应包含 fpath 注册和 compdef 声明。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion
    install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    plugin_zsh = (plugin_dir / "agent-kit.plugin.zsh").read_text(encoding="utf-8")
    assert "fpath=" in plugin_zsh
    assert "compdef" in plugin_zsh
    assert "ak" in plugin_zsh


def test_install_zfunc_creates_completion_file(monkeypatch, tmp_path):
    """当 oh-my-zsh 不存在时，应将补全脚本写入 ~/.zfunc/_agent-kit。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion
    result = install_zsh_completion(home=tmp_path)
    zfunc_file = tmp_path / ".zfunc" / "_agent-kit"
    assert zfunc_file.exists()
    assert result.method == "zfunc"


def test_install_zfunc_script_contains_complete_env_var(monkeypatch, tmp_path):
    """标准路径安装的补全脚本应包含 _AGENT_KIT_COMPLETE 环境变量。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion
    install_zsh_completion(home=tmp_path)
    content = (tmp_path / ".zfunc" / "_agent-kit").read_text(encoding="utf-8")
    assert "_AGENT_KIT_COMPLETE" in content


def test_remove_omz_deletes_plugin_dir(monkeypatch, tmp_path):
    """卸载应删除 oh-my-zsh 插件目录。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion, remove_zsh_completion
    install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    assert plugin_dir.exists()
    result = remove_zsh_completion(home=tmp_path)
    assert not plugin_dir.exists()
    assert result.removed is True


def test_remove_zfunc_deletes_completion_file(monkeypatch, tmp_path):
    """卸载应删除 ~/.zfunc/_agent-kit 文件。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion, remove_zsh_completion
    install_zsh_completion(home=tmp_path)
    zfunc_file = tmp_path / ".zfunc" / "_agent-kit"
    assert zfunc_file.exists()
    result = remove_zsh_completion(home=tmp_path)
    assert not zfunc_file.exists()
    assert result.removed is True


def test_remove_when_not_installed_returns_not_removed(monkeypatch, tmp_path):
    """当补全未安装时，卸载应返回 removed=False 而非报错。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import remove_zsh_completion
    result = remove_zsh_completion(home=tmp_path)
    assert result.removed is False


def test_install_is_idempotent(monkeypatch, tmp_path):
    """重复安装应覆盖已有文件而非报错。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion
    result1 = install_zsh_completion(home=tmp_path)
    result2 = install_zsh_completion(home=tmp_path)
    plugin_dir = custom_dir / "plugins" / "agent-kit"
    assert (plugin_dir / "_agent-kit").exists()
    assert (plugin_dir / "agent-kit.plugin.zsh").exists()


def test_completion_script_contains_managed_marker():
    """补全脚本应包含 managed marker 以便卸载时识别。"""
    from agent_kit.completion import generate_zsh_completion_script, MANAGED_COMPLETION_MARKER
    script = generate_zsh_completion_script()
    assert MANAGED_COMPLETION_MARKER in script


def test_omz_plugin_zsh_contains_managed_marker():
    """oh-my-zsh 插件入口应包含 managed marker。"""
    from agent_kit.completion import generate_omz_plugin_zsh, MANAGED_COMPLETION_MARKER
    content = generate_omz_plugin_zsh()
    assert MANAGED_COMPLETION_MARKER in content


def test_omz_plugin_zsh_registers_ak_alias():
    """oh-my-zsh 插件入口应同时注册 agent-kit 和 ak 两个命令的补全。"""
    from agent_kit.completion import generate_omz_plugin_zsh
    content = generate_omz_plugin_zsh()
    assert "agent-kit" in content
    assert "ak" in content
    assert "compdef" in content


def test_installed_omz_completion_file_matches_generated_script(monkeypatch, tmp_path):
    """安装到 oh-my-zsh 的 _agent-kit 文件内容应与生成的脚本一致。"""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setenv("ZSH_CUSTOM", str(custom_dir))
    from agent_kit.completion import install_zsh_completion, generate_zsh_completion_script
    install_zsh_completion(home=tmp_path)
    installed = (custom_dir / "plugins" / "agent-kit" / "_agent-kit").read_text(encoding="utf-8")
    expected = generate_zsh_completion_script()
    assert installed == expected


def test_installed_zfunc_file_matches_generated_script(monkeypatch, tmp_path):
    """安装到 ~/.zfunc 的 _agent-kit 文件内容应与生成的脚本一致。"""
    monkeypatch.delenv("ZSH_CUSTOM", raising=False)
    from agent_kit.completion import install_zsh_completion, generate_zsh_completion_script
    install_zsh_completion(home=tmp_path)
    installed = (tmp_path / ".zfunc" / "_agent-kit").read_text(encoding="utf-8")
    expected = generate_zsh_completion_script()
    assert installed == expected


def test_completion_translation_keys_exist_in_english():
    """所有 completion 相关翻译键应存在于英文 catalog 中。"""
    from agent_kit.messages import MESSAGES
    en = MESSAGES["en"]
    required_keys = [
        "completion.help",
        "completion.install.help",
        "completion.show.help",
        "completion.remove.help",
        "completion.install.omz",
        "completion.install.zfunc",
        "completion.remove.done",
        "completion.remove.not_found",
        "completion.shell.unsupported",
    ]
    for key in required_keys:
        assert key in en, f"Missing English translation key: {key}"


def test_completion_translation_keys_exist_in_chinese():
    """所有 completion 相关翻译键应存在于中文 catalog 中。"""
    from agent_kit.messages import MESSAGES
    zh = MESSAGES["zh-CN"]
    required_keys = [
        "completion.help",
        "completion.install.help",
        "completion.show.help",
        "completion.remove.help",
        "completion.install.omz",
        "completion.install.zfunc",
        "completion.remove.done",
        "completion.remove.not_found",
        "completion.shell.unsupported",
    ]
    for key in required_keys:
        assert key in zh, f"Missing Chinese translation key: {key}"


def test_completion_translation_keys_consistent_between_en_and_zh():
    """英文和中文的 completion 翻译键集合应一致。"""
    from agent_kit.messages import MESSAGES
    en_keys = {k for k in MESSAGES["en"] if k.startswith("completion.")}
    zh_keys = {k for k in MESSAGES["zh-CN"] if k.startswith("completion.")}
    assert en_keys == zh_keys
