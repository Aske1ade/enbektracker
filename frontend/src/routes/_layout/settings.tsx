import {
  Box,
  Container,
  Heading,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
} from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"

import Appearance from "../../components/UserSettings/Appearance"
import AdvancedProfile from "../../components/UserSettings/AdvancedProfile"
import ChangePassword from "../../components/UserSettings/ChangePassword"
import NotificationSettings from "../../components/UserSettings/NotificationPreferences"
import UserInformation from "../../components/UserSettings/UserInformation"

function CombinedProfile() {
  return (
    <Box>
      <UserInformation />
      <Box mt={6} pt={6} borderTopWidth="1px" borderColor="ui.border">
        <AdvancedProfile />
      </Box>
    </Box>
  )
}

const tabsConfig = [
  { title: "Профиль", component: CombinedProfile },
  { title: "Уведомления", component: NotificationSettings },
  { title: "Безопасность", component: ChangePassword },
  { title: "Тема", component: Appearance },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
})

function UserSettings() {
  const finalTabs = tabsConfig

  return (
    <Container maxW="full">
      <Heading size="lg" textAlign={{ base: "center", md: "left" }} py={8}>
        Настройки пользователя
      </Heading>
      <Tabs variant="enclosed">
        <TabList>
          {finalTabs.map((tab, index) => (
            <Tab key={index}>{tab.title}</Tab>
          ))}
        </TabList>
        <TabPanels>
          {finalTabs.map((tab, index) => (
            <TabPanel key={index}>
              <tab.component />
            </TabPanel>
          ))}
        </TabPanels>
      </Tabs>
    </Container>
  )
}
