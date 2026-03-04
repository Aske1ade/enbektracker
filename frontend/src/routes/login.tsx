import { ViewIcon, ViewOffIcon } from "@chakra-ui/icons"
import {
  Box,
  Button,
  Flex,
  FormControl,
  FormErrorMessage,
  FormLabel,
  HStack,
  IconButton,
  Input,
  InputGroup,
  InputRightElement,
  Text,
  useBoolean,
} from "@chakra-ui/react"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { type SubmitHandler, useForm } from "react-hook-form"

import type { Body_login_login_access_token as AccessToken } from "../client"
import useAuth, { isLoggedIn } from "../hooks/useAuth"
import { emailPattern } from "../utils"

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
})

function Login() {
  const [show, setShow] = useBoolean()
  const { loginMutation, error, resetError } = useAuth()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AccessToken>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit: SubmitHandler<AccessToken> = async (data) => {
    if (isSubmitting) return
    resetError()
    try {
      await loginMutation.mutateAsync(data)
    } catch {
      // handled in useAuth
    }
  }

  return (
    <Flex
      minH="100vh"
      bg="linear-gradient(165deg, #F2F7FF 0%, #E9F1FC 55%, #F8FBFF 100%)"
    >
      <Flex
        flex="1"
        display={{ base: "none", lg: "flex" }}
        direction="column"
        justify="space-between"
        p={12}
        bg="linear-gradient(180deg, #1F4773 0%, #2E5E90 100%)"
        color="white"
      >
        <Box>
          <Box
            as="img"
            src="/9d3e6ca7e9bbef28331ec81c8a207f91.png"
            alt="АО «Центр развития трудовых ресурсов»"
            w="290px"
            h="68px"
            objectFit="contain"
            filter="brightness(0) invert(1)"
          />
          <Text fontSize="3xl" fontWeight="700" mt={2}>
            Enbek Tracker
          </Text>
        </Box>
        <Box>
          <HStack align="center" spacing={3}>
            <Box
              as="img"
              src="/Emblem_of_Kazakhstan_latin.svg"
              alt="Эмблема Республики Казахстан"
              w="34px"
              h="34px"
              objectFit="contain"
            />
            <Text fontSize="lg" fontWeight="600" lineHeight="1.3">
              Министерство труда и социальной защиты населения Республики
              Казахстан
            </Text>
          </HStack>
          <Text mt={3} fontSize="sm" opacity={0.85}>
            Корпоративная платформа управления задачами, проектами и
            исполнительской дисциплиной.
          </Text>
        </Box>
      </Flex>

      <Flex flex="1" align="center" justify="center" p={{ base: 4, md: 8 }}>
        <Box
          as="form"
          onSubmit={handleSubmit(onSubmit)}
          w="full"
          maxW="460px"
          bg="rgba(255,255,255,0.92)"
          backdropFilter="blur(8px)"
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="12px"
          p={{ base: 5, md: 8 }}
          boxShadow="0 18px 40px rgba(30,58,95,0.12)"
        >
          <Text fontSize="xs" color="ui.muted" letterSpacing="0.08em">
            ВХОД В СИСТЕМУ
          </Text>
          <Text fontSize="2xl" fontWeight="700" mt={1} mb={6}>
            Enbek Tracker
          </Text>

          <FormControl id="username" isInvalid={!!errors.username || !!error}>
            <FormLabel>Email</FormLabel>
            <Input
              id="username"
              {...register("username", { pattern: emailPattern })}
              placeholder="admin@example.com"
              type="email"
              required
            />
            {errors.username && (
              <FormErrorMessage>{errors.username.message}</FormErrorMessage>
            )}
          </FormControl>

          <FormControl id="password" mt={4} isInvalid={!!error}>
            <FormLabel>Пароль</FormLabel>
            <InputGroup>
              <Input
                {...register("password")}
                type={show ? "text" : "password"}
                placeholder="Введите пароль"
                required
              />
              <InputRightElement>
                <IconButton
                  aria-label={show ? "Скрыть пароль" : "Показать пароль"}
                  variant="ghost"
                  size="sm"
                  onClick={setShow.toggle}
                  icon={show ? <ViewOffIcon /> : <ViewIcon />}
                />
              </InputRightElement>
            </InputGroup>
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>

          <Button
            mt={6}
            type="submit"
            isLoading={isSubmitting}
            w="full"
            size="md"
          >
            Войти
          </Button>
        </Box>
      </Flex>
    </Flex>
  )
}
