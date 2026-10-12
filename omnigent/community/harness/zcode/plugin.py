"""Import-light registration for the community harness registry."""

from omnigent.harness_capabilities import (
    AuthModel,
    EffortFamily,
    Elicitation,
    HarnessCapabilities,
    InstructionDelivery,
    IntegrationMode,
    ModelFamily,
    Resume,
)
from omnigent.harness_install_spec import HarnessInstallSpec
from omnigent.harness_plugins import HarnessContribution


def get_contribution() -> HarnessContribution:
    return HarnessContribution(
        name="omnigent-zcode",
        valid_harnesses=frozenset({"zcode"}),
        harness_modules={"zcode": "omnigent.community.harness.zcode.zcode_harness"},
        aliases={"z-code": "zcode"},
        harness_labels={"zcode": "ZCode"},
        install_specs={
            "zcode": HarnessInstallSpec(
                display="ZCode",
                binary="zcode",
                package=None,
                login_args=("login",),
                install_hint="Install ZCode from https://github.com/zai-org/zcode",
            ),
        },
        harness_install_keys={"zcode": "zcode", "z-code": "zcode"},
        model_env_keys={"zcode": "HARNESS_ZCODE_MODEL"},
        spawn_env_builders={"zcode": "omnigent.community.harness.zcode.spawn_env:build_spawn_env"},
        capabilities={
            "zcode": HarnessCapabilities(
                integration_mode=IntegrationMode.CLI_SUBPROCESS,
                elicitation=Elicitation.NONE,
                resume=Resume.WARM_REATTACH,
                effort=EffortFamily.NONE,
                model_family=ModelFamily.MULTI,
                auth=AuthModel.OWN_AUTH,
                subagents=False,
                interrupt=True,
                streaming=True,
                steering=False,
                images=True,
                compaction=False,
                instruction_delivery=InstructionDelivery.FIRST_USER_PREFIX,
            ),
        },
    )
