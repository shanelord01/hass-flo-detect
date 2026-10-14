"""Config flow for the Flo Detect integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_FLO_ENTRY_ID, DOMAIN, FLO_DOMAIN


class FloDetectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add Flo Detect for a Flo config entry."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the Flo config entry whose devices report Flo Detect events."""
        flo_entries = [
            flo_entry
            for flo_entry in self.hass.config_entries.async_entries(FLO_DOMAIN)
            if flo_entry.state is ConfigEntryState.LOADED
        ]
        if not flo_entries:
            return self.async_abort(reason="flo_not_loaded")

        if user_input is not None:
            flo_entry_id = user_input[CONF_FLO_ENTRY_ID]
            await self.async_set_unique_id(flo_entry_id)
            self._abort_if_unique_id_configured()
            flo_entry = self.hass.config_entries.async_get_entry(flo_entry_id)
            title = flo_entry.title if flo_entry else flo_entry_id
            return self.async_create_entry(
                title=f"Flo Detect ({title})",
                data={CONF_FLO_ENTRY_ID: flo_entry_id},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_FLO_ENTRY_ID, default=flo_entries[0].entry_id
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=flo_entry.entry_id, label=flo_entry.title
                                )
                                for flo_entry in flo_entries
                            ]
                        )
                    )
                }
            ),
        )
