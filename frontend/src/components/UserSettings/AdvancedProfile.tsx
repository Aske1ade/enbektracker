import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  Heading,
  Input,
  Select,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useEffect, useState } from "react"

import useAuth from "../../hooks/useAuth"
import useCustomToast from "../../hooks/useCustomToast"
import {
  type AdvancedProfilePreferences,
  readAdvancedProfilePreferences,
  writeAdvancedProfilePreferences,
} from "../../hooks/useUserPreferences"

const AdvancedProfile = () => {
  const { user } = useAuth()
  const showToast = useCustomToast()
  const [form, setForm] = useState<AdvancedProfilePreferences>(
    readAdvancedProfilePreferences(user?.id),
  )

  useEffect(() => {
    setForm(readAdvancedProfilePreferences(user?.id))
  }, [user?.id])

  const save = () => {
    writeAdvancedProfilePreferences(user?.id, form)
    showToast.success("Успешно", "Расширенные настройки профиля сохранены")
  }

  return (
    <Box>
      <Heading size="sm" py={4}>
        Расширенный профиль
      </Heading>
      <VStack align="stretch" spacing={3}>
        <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
          <GridItem>
            <FormControl>
              <FormLabel>Должность</FormLabel>
              <Input
                value={form.position}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, position: event.target.value }))
                }
                placeholder="Например: Руководитель проекта"
              />
            </FormControl>
          </GridItem>
          <GridItem>
            <FormControl>
              <FormLabel>Телефон</FormLabel>
              <Input
                value={form.phone}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, phone: event.target.value }))
                }
                placeholder="+7 ..."
              />
            </FormControl>
          </GridItem>
          <GridItem>
            <FormControl>
              <FormLabel>Telegram</FormLabel>
              <Input
                value={form.telegram}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, telegram: event.target.value }))
                }
                placeholder="@username"
              />
            </FormControl>
          </GridItem>
          <GridItem>
            <FormControl>
              <FormLabel>Язык интерфейса</FormLabel>
              <Select
                value={form.locale}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, locale: event.target.value }))
                }
              >
                <option value="ru-RU">Русский</option>
                <option value="kk-KZ">Қазақша</option>
                <option value="en-US">English</option>
              </Select>
            </FormControl>
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2 }}>
            <FormControl>
              <FormLabel>Часовой пояс</FormLabel>
              <Select
                value={form.timezone}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, timezone: event.target.value }))
                }
              >
                <option value="Asia/Almaty">Asia/Almaty (UTC+5)</option>
                <option value="Asia/Aqtau">Asia/Aqtau (UTC+5)</option>
                <option value="Asia/Aqtobe">Asia/Aqtobe (UTC+5)</option>
                <option value="Asia/Qyzylorda">Asia/Qyzylorda (UTC+5)</option>
                <option value="UTC">UTC</option>
              </Select>
            </FormControl>
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2 }}>
            <FormControl>
              <FormLabel>Подпись по умолчанию</FormLabel>
              <Textarea
                value={form.signature}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, signature: event.target.value }))
                }
                placeholder="Добавляется в комментарии/отчёты при необходимости"
                minH="120px"
              />
            </FormControl>
          </GridItem>
        </Grid>

        <Button alignSelf="start" onClick={save}>
          Сохранить расширенный профиль
        </Button>

        <Text fontSize="xs" color="ui.muted">
          Поля расширенного профиля сохраняются локально для текущего аккаунта.
        </Text>
      </VStack>
    </Box>
  )
}

export default AdvancedProfile
