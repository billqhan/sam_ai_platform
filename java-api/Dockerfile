# Multi-stage build for Java Spring Boot application
# Builder uses Maven with Corretto 21 preinstalled to avoid apk issues
FROM maven:3.9-amazoncorretto-21 AS builder

# Set working directory
WORKDIR /app

# Copy project files and build
COPY pom.xml .
COPY src ./src

# Build the application (skip tests for faster image builds)
RUN mvn -B clean package -DskipTests

# Runtime stage (Debian-based Corretto to avoid apk)
FROM amazoncorretto:21

# Set working directory
WORKDIR /app

# Copy the built JAR from builder stage
COPY --from=builder /app/target/rfp-response-agent-api-*.jar /app/app.jar

# Expose port
EXPOSE 8080

# JVM optimization for containers
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:+UseG1GC -XX:+UseStringDeduplication"

# Start the application
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar --spring.profiles.active=aws --spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration"]