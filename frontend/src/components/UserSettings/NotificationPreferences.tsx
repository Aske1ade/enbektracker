import {
  Box,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  Heading,
  Input,
  Switch,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useEffect, useState } from "react"

import useAuth from "../../hooks/useAuth"
import {
  type NotificationPreferences,
  readNotificationPreferences,
  writeNotificationPreferences,
} from "../../hooks/useUserPreferences"

const NotificationSettings = () => {
  const { user } = useAuth()
  const [prefs, setPrefs] = useState<NotificationPreferences>(
    readNotificationPreferences(user?.id),
  )

  useEffect(() => {
    setPrefs(readNotificationPreferences(user?.id))
  }, [user?.id])

  const updatePrefs = (patch: Partial<NotificationPreferences>) => {
    const next = { ...prefs, ...patch }
    setPrefs(next)
    writeNotificationPreferences(user?.id, next)
  }

  return (
    <Box>
      <Heading size="sm" py={4}>
        Уведомления
      </Heading>
      <VStack align="stretch" spacing={3}>
        <ToggleRow
          label="Включить desktop-уведомления"
          value={prefs.desktop_enabled}
          onChange={(value) => updatePrefs({ desktop_enabled: value })}
        />
        <ToggleRow
          label="Звук уведомлений"
          value={prefs.sound_enabled}
          onChange={(value) => updatePrefs({ sound_enabled: value })}
          isDisabled={!prefs.desktop_enabled}
        />
        <ToggleRow
          label="Событие: назначена задача"
          value={prefs.assignment_enabled}
          onChange={(value) => updatePrefs({ assignment_enabled: value })}
          isDisabled={!prefs.desktop_enabled}
        />
        <ToggleRow
          label="Событие: срок близко"
          value={prefs.due_soon_enabled}
          onChange={(value) => updatePrefs({ due_soon_enabled: value })}
          isDisabled={!prefs.desktop_enabled}
        />
        <ToggleRow
          label="Событие: просрочена"
          value={prefs.overdue_enabled}
          onChange={(value) => updatePrefs({ overdue_enabled: value })}
          isDisabled={!prefs.desktop_enabled}
        />
        <ToggleRow
          label="Событие: изменён статус"
          value={prefs.status_enabled}
          onChange={(value) => updatePrefs({ status_enabled: value })}
          isDisabled={!prefs.desktop_enabled}
        />
        <ToggleRow
          label="Тихие часы"
          value={prefs.quiet_hours_enabled}
          onChange={(value) => updatePrefs({ quiet_hours_enabled: value })}
          isDisabled={!prefs.desktop_enabled}
        />

        <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
          <GridItem>
            <FormControl isDisabled={!prefs.quiet_hours_enabled}>
              <FormLabel>Тихие часы: c</FormLabel>
              <Input
                type="time"
                value={prefs.quiet_hours_from}
                onChange={(event) =>
                  updatePrefs({ quiet_hours_from: event.target.value })
                }
              />
            </FormControl>
          </GridItem>
          <GridItem>
            <FormControl isDisabled={!prefs.quiet_hours_enabled}>
              <FormLabel>Тихие часы: до</FormLabel>
              <Input
                type="time"
                value={prefs.quiet_hours_to}
                onChange={(event) =>
                  updatePrefs({ quiet_hours_to: event.target.value })
                }
              />
            </FormControl>
          </GridItem>
        </Grid>

        <Text fontSize="xs" color="ui.muted">
          Настройки сохраняются локально для текущего пользователя и применяются
          к интерфейсу desktop-событий.
        </Text>
      </VStack>
    </Box>
  )
}

function ToggleRow({
  label,
  value,
  onChange,
  isDisabled,
}: {
  label: string
  value: boolean
  onChange: (value: boolean) => void
  isDisabled?: boolean
}) {
  return (
    <FormControl display="flex" justifyContent="space-between" alignItems="center">
      <FormLabel m={0}>{label}</FormLabel>
      <Switch
        isChecked={value}
        onChange={(event) => onChange(event.target.checked)}
        isDisabled={isDisabled}
      />
    </FormControl>
  )
}

export default NotificationSettings
